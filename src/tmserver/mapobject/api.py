import os.path as p
import json
import logging
from cStringIO import StringIO
from zipfile import ZipFile

from flask.ext.jwt import jwt_required
from flask.ext.jwt import current_identity
from flask.ext.jwt import jwt_required
from flask import jsonify, request, send_file
from sqlalchemy.sql import text
from werkzeug import secure_filename

from tmlib.models import (
    MapobjectSegmentation, MapobjectType, Mapobject,
    Experiment, Plate, Well, Site
)

from tmserver.api import api
from tmserver.extensions import db
from tmserver.util import extract_model_from_path
from tmserver.error import MalformedRequestError


logger = logging.getLogger(__name__)


@api.route('/experiments/<experiment_id>/mapobjects/<object_name>/tile', methods=['GET'])
@extract_model_from_path(Experiment)
def get_mapobjects_tile(experiment, object_name):

    # The coordinates of the requested tile
    x = request.args.get('x')
    y = request.args.get('y')
    # "z" is the pyramid zoom level and "zlevel" the z-resolution of the
    # acquired image
    z = request.args.get('z')
    zplane = request.args.get('zplane')
    tpoint = request.args.get('tpoint')
    # Check arguments for validity and convert to integers
    if any([var is None for var in [x, y, z, zplane, tpoint]]):
        raise MalformedRequestError('Missing request arguments.')
    else:
        x, y, z, zplane, tpoint = map(int, [x, y, z, zplane, tpoint])

    logger.debug(
        'get mapobject tile: x=%d, y=%d, z=%d, zplane=%d, tpoint=%d',
        x, y, z, zplane, tpoint
    )

    if object_name == 'DEBUG_TILE':
        maxzoom = experiment.channels[0].layers[0].maxzoom_level_index
        minx, miny, maxx, maxy = MapobjectSegmentation.bounding_box(x, y, z, maxzoom)
        return jsonify({
            'type': 'Feature',
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[
                    [maxx, maxy], [minx, maxy], [minx, miny], [maxx, miny],
                    [maxx, maxy]
                ]]
            },
            'properties': {
                'x': x,
                'y': y,
                'z': z,
                'type': 'DEBUG_TILE'
            }
        })

    mapobject_type = db.session.query(MapobjectType).\
        filter_by(name=object_name, experiment_id=experiment.id).\
        one()
    query_res = mapobject_type.get_mapobject_outlines_within_tile(
        x, y, z, tpoint, zplane
    )

    features = []

    if len(query_res) > 0:
        # Try to estimate how many points there are in total within
        # the polygons of this tile.
        # TODO: Make this more light weight by sending binary coordinates
        # without GEOJSON overhead. Requires a hack on the client side.
        for mapobject_id, geom_geojson_str in query_res:
            feature = {
                "type": "Feature",
                "id": mapobject_id,
                "geometry": json.loads(geom_geojson_str),
                "properties": {
                    "type": object_name
                }
            }
            features.append(feature)

    return jsonify({
        "type": "FeatureCollection",
        "features": features
    })


@api.route('/experiments/<experiment_id>/mapobjects/<object_name>/segmentations', methods=['GET'])
@jwt_required()
@extract_model_from_path(Experiment)
def get_mapobjects_segmentation(experiment, object_name):
    well_name = request.args.get('well_name')
    x = request.args.get('x')
    y = request.args.get('y')
    zplane = request.args.get('zplane')
    tpoint = request.args.get('tpoint')
    site = db.session.query(Site).\
        join(Well).\
        filter(
            Well.plate_id == cycle.id, Well.name == well_name,
            Site.x == x, Site.y == y
        ).\
        one()
    mapobject_type = db.session.query(MapobjectType).\
        filter_by(name=object_name, experiment_id=experiment.id).\
        one()
    segmentation = db.session.query(
            MapobjectSegmentation.label,
            MapobjectSegmentation.geom_poly
        ).\
        join(MapobjectType).\
        filter(
            MapobjectType.name == object_name,
            MapobjectType.experiment_id == experiment.id,
            MapobjectSegmentation.site_id == site.id,
            MapobjectSegmentation.zplane == zplane,
            MapobjectSegmentation.tpoint == tpoint
        )
    array = np.zeros((site.height, site.width), np.uint16)
    for seg in segmentation:
        poly = to_shape(seg.geom_poly)
        coordinates = np.array(poly.exterior.coords).astype(int)
        x, y = np.split(coordinates, 2, axis=1)
        x -= site.offset[1]
        y -= site.offset[0]
        y, x = skimage.draw.polygon(y, x)
        array[y, x] = seg.label
    f = StringIO()
    f.write(cv2.imencode('.png', array)[1])
    f.seek(0)
    filename = '%s_%s_x%3d_y%3d_z%3d_t%3d_%s.png' % (
        experiment.name, site.well.name, site.x, site.y, zplane, tpoint,
        object_name
    )
    return send_file(
        f,
        attachment_filename=secure_filename(filename),
        mimetype='image/png',
        as_attachement=True
    )


@api.route('/experiments/<experiment_id>/mapobjects/<object_name>/features',
        methods=['GET'])
@jwt_required()
@extract_model_from_path(Experiment)
def get_feature_values(experiment, object_name):
    mapobject_type = db.session.query(MapobjectType).\
        filter_by(experiment_id=experiment.id, name=object_name).\
        one()
    features = mapobject_type.get_feature_value_matrix()
    metadata = mapobject_type.get_metadata_matrix()
    if features.values.shape[0] != metadata.values.shape[0]:
        raise ValueError(
            'Features and metadata must have same number of "%s" objects'
            % object_name
        )
    if any(features.index.values != metadata.index.values):
        raise ValueError(
            'Features and metadata must have the same index.'
        )
    basename = secure_filename(
        '%s_%s_features' % (experiment.name, object_name)
    )
    data_filename = '%s_data.csv' % basename
    metadata_filename = '%s_metadata.csv' % basename
    f = StringIO()
    with ZipFile(f, 'w') as zf:
        zf.writestr(
            data_filename,
            features.to_csv(None, encoding='utf-8', index=False)
        )
        zf.writestr(
            metadata_filename,
            metadata.to_csv(None, encoding='utf-8', index=False)
        )
    f.seek(0)
    return send_file(
        f,
        attachment_filename='%s.zip' % basename,
        mimetype='application/octet-stream',
        as_attachment=True
    )
