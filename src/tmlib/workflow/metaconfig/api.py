import os
import logging
import numpy as np
import pandas as pd
import bioformats

import tmlib.models as tm
from tmlib.workflow.metaconfig import metadata_handler_factory
from tmlib.workflow.metaconfig import metadata_reader_factory
from tmlib.workflow.api import ClusterRoutines
from tmlib.errors import MetadataError
from tmlib.workflow import register_api

logger = logging.getLogger(__name__)


@register_api('metaconfig')
class MetadataConfigurator(ClusterRoutines):

    '''Class for configuration of microscope image metadata.

    It provides methods for conversion of metadata extracted from heterogeneous
    microscope file formats using the
    `Bio-Formats <http://www.openmicroscopy.org/site/products/bio-formats>`_
    library into a custom format. The original metadata has to be available
    in OMEXML format according to the
    `OME schema <http://www.openmicroscopy.org/Schemas/Documentation/Generated/OME-2015-01/ome.html>`_.

    The class further provides methods to complement the automatically
    retrieved metadata by making use of additional microscope-specific metadata
    files and/or user input.

    The metadata corresponding to the final PNG images are stored in a
    separate JSON file.
    '''

    def __init__(self, experiment_id, verbosity, **kwargs):
        '''
        Parameters
        ----------
        experiment_id: int
            ID of the processed experiment
        verbosity: int
            logging level
        **kwargs: dict
            ignored keyword arguments
        '''
        super(MetadataConfigurator, self).__init__(experiment_id, verbosity)

    def create_batches(self, args):
        '''Creates job descriptions for parallel computing.

        Parameters
        ----------
        args: tmlib.workflow.metaconfig.args.MetaconfigInitArgs
            step-specific arguments

        Returns
        -------
        Dict[str, List[dict] or dict]
            job descriptions
        '''
        job_descriptions = dict()
        job_descriptions['run'] = list()
        job_count = 0
        with tm.utils.Session() as session:
            acquisitions = session.query(tm.Acquisition).\
                join(tm.Plate).\
                join(tm.Experiment).\
                filter(tm.Experiment.id == self.experiment_id).\
                all()
            for acq in acquisitions:
                job_count += 1
                description = {
                    'id': job_count,
                    'inputs': {
                        'microscope_metadata_files': [
                            os.path.join(
                                acq.microscope_metadata_location, f.name
                            )
                            for f in acq.microscope_metadata_files
                        ]
                    },
                    'outputs': dict(),
                    'microscope_image_file_ids': [
                        f.id for f in acq.microscope_image_files
                    ],
                    'microscope_type': acq.plate.experiment.microscope_type,
                    'regex': args.regex,
                    'acquisition_id': acq.id,
                    'stitch_major_axis': args.stitch_major_axis,
                    'n_vertical': args.n_vertical,
                    'n_horizontal': args.n_horizontal,
                    'stitch_layout': args.stitch_layout
                }
                job_descriptions['run'].append(description)

            job_descriptions['collect'] = {
                'inputs': dict(),
                'outputs': dict()
            }

        return job_descriptions

    def delete_previous_job_output(self):
        '''Deletes all instances of class :py:class:`tm.Cycle`,
        :py:class:`tm.Well`, and :py:class:`tm.Channel` as
        well as all children for the processed experiment.
        '''
        with tm.utils.Session() as session:

            plate_ids = session.query(tm.Plate.id).\
                filter_by(experiment_id=self.experiment_id).\
                all()
            plate_ids = [p[0] for p in plate_ids]

        with tm.utils.Session() as session:

            logger.info('delete existing cycles')
            session.query(tm.Cycle).\
                filter(tm.Cycle.plate_id.in_(plate_ids)).\
                delete()

        with tm.utils.Session() as session:

            logger.info('delete existing wells')
            session.query(tm.Well).\
                filter(tm.Well.plate_id.in_(plate_ids)).\
                delete()

        with tm.utils.Session() as session:

            logger.info('delete existing channels')
            session.query(tm.Channel).\
                filter(tm.Channel.experiment_id == self.experiment_id).\
                delete()

    def run_job(self, batch):
        '''Formats OMEXML metadata extracted from microscope image files and
        complement it with metadata retrieved from additional microscope
        metadata files and/or user input.

        The actual processing is done by an implementation of the
        :py:class:`tmlib.workflow.metaconfig.default.MetadataHandler` abstract
        base class. Some file formats require additional customization,
        either because the `Bio-Formats` library does not fully support them or
        because the microscopes provides insufficient information in the files.
        To overcome these limitations, one can create a custom subclass
        of the `MetaHandler` abstract base class and overwrite its
        *ome_additional_metadata* property. Custom handlers already exists for
        the Yokogawa CellVoyager 7000 microscope ("cellvoyager")
        and Visitron microscopes ("visiview"). The list of custom
        handlers can be further extended by creating a new module in the
        `metaconfig` package with the same name as the corresponding file
        format. The module must contain a custom implementation of
        :py:class:`tmlib.workflow.metaconfig.default.MetadataHandler`,
        whose name has to be pretended with the capitalized name of the file
        format.

        See also
        --------
        :py:mod:`tmlib.workflow.metaconfig.default`
        :py:mod:`tmlib.workflow.metaconfig.cellvoyager`
        :py:mod:`tmlib.workflow.metaconfig.visiview`
        '''
        MetadataReader = metadata_reader_factory(batch['microscope_type'])

        with tm.utils.Session() as session:
            acquisition = session.query(tm.Acquisition).\
                get(batch['acquisition_id'])
            metadata_filenames = [
                f.location for f in acquisition.microscope_metadata_files
            ]
            omexml_images = {
                f.name: bioformats.OMEXML(f.omexml)
                for f in acquisition.microscope_image_files
            }

        with MetadataReader() as mdreader:
            omexml_metadata = mdreader.read(
                metadata_filenames, omexml_images.keys()
            )

        MetadataHandler = metadata_handler_factory(batch['microscope_type'])
        mdhandler = MetadataHandler(omexml_images, omexml_metadata)
        mdhandler.configure_omexml_from_image_files()
        mdhandler.configure_omexml_from_metadata_files(batch['regex'])
        missing = mdhandler.determine_missing_metadata()
        if missing:
            logger.warning('required metadata information is missing')
            logger.info(
                'try to retrieve missing metadata from filenames '
                'using regular expression'
            )
            with tm.utils.Session() as session:
                experiment = session.query(tm.Experiment).get(self.experiment_id)
                plate_dimensions = experiment.plates[0].dimensions
            mdhandler.configure_metadata_from_filenames(
                plate_dimensions=plate_dimensions,
                regex=batch['regex']
            )
            if (batch['regex'] is None and
                    mdhandler.IMAGE_FILE_REGEX_PATTERN is None):
                logger.warning(
                    'The following metadata information is missing: "%s"'
                    'You can provide a regular expression in order to '
                    'retrieve the missing information from filenames.'
                    % '", "'.join(missing)
                )
        missing = mdhandler.determine_missing_metadata()
        if missing:
            raise MetadataError(
                'The following metadata information is missing:\n"%s"\n'
                % '", "'.join(missing)
            )
        # Once we have collected basic metadata such as information about
        # channels and focal planes, we try to determine the relative position
        # of images within the acquisition grid
        try:
            logger.info(
                'try to determine grid coordinates from microscope '
                'stage positions'
            )
            mdhandler.determine_grid_coordinates_from_stage_positions()
        except MetadataError as error:
            logger.warning(
                'microscope stage positions are not available: "%s"'
                % str(error)
            )
            logger.info(
                'try to determine grid coordinates from provided stitch layout'
            )
            mdhandler.determine_grid_coordinates_from_layout(
                stitch_layout=batch['stitch_layout'],
                stitch_major_axis=batch['stitch_major_axis'],
                stitch_dimensions=(batch['n_vertical'], batch['n_horizontal'])
            )

        mdhandler.group_metadata_per_zstack()

        # Create consistent zero-based ids
        # (some microscopes use one-based indexing)
        mdhandler.update_channel()
        mdhandler.update_zplane()
        mdhandler.assign_acquisition_site_indices()
        md = mdhandler.remove_redundant_columns()
        fmap = mdhandler.create_image_file_mapping()
        with tm.utils.Session() as session:
            acquisition = session.query(tm.Acquisition).\
                get(batch['acquisition_id'])

            for w in np.unique(md.well_name):
                w_index = np.where(md.well_name == w)[0]
                well = session.get_or_create(
                    tm.Well,
                    plate_id=acquisition.plate.id, name=w
                )

                for s in np.unique(md.loc[w_index, 'site']):
                    s_index = np.where(md.site == s)[0]
                    y = md.loc[s_index, 'well_position_y'].values[0]
                    x = md.loc[s_index, 'well_position_x'].values[0]
                    height = md.loc[s_index, 'height'].values[0]
                    width = md.loc[s_index, 'width'].values[0]
                    site = session.get_or_create(
                        tm.Site,
                        y=y, x=x, height=height, width=width, well_id=well.id
                    )

                    for index, i in md.ix[s_index].iterrows():
                        session.get_or_create(
                            tm.ImageFileMapping,
                            tpoint=i.tpoint,
                            site_id=site.id, map=fmap[index],
                            wavelength=i.channel_name,
                            bit_depth=i.bit_depth,
                            acquisition_id=acquisition.id
                        )

    def collect_job_output(self, batch):
        '''Assigns registered image files from different acquisitions to
        separate *cycles*. If an acquisition includes multiple time points,
        a separate *cycle* is created for each time point.
        The mapping from *acquisitions* to *cycles* is consequently
        1 -> n, where n is the number of time points per acquisition (n >= 1).

        Whether acquisition time points will be interpreted as actual
        time points in a time series depends on the value of
        :py:attribute:`tm.Experiment.plate_acquisition_mode`.

        Parameters
        ----------
        batch: dict
            description of the *collect* job
        '''
        with tm.utils.Session() as session:
            # We need to do this per plate to ensure correct indices
            # TODO: check plates have similar channels, etc
            plates = session.query(tm.Plate).\
                filter_by(experiment_id=self.experiment_id)
            for plt in plates:
                t_index = 0
                w_index = 0
                c_index = 0
                acquisitions = session.query(tm.Acquisition).\
                    filter_by(plate_id=plt.id)
                for acq in acquisitions:
                    is_time_series_experiment = \
                        acq.plate.experiment.plate_acquisition_mode == 'basic'
                    is_multiplexing_experiment = \
                        acq.plate.experiment.plate_acquisition_mode == 'multiplexing'
                    df = pd.DataFrame(
                        session.query(
                            tm.ImageFileMapping.tpoint,
                            tm.ImageFileMapping.wavelength,
                            tm.ImageFileMapping.bit_depth
                        ).
                        filter(tm.ImageFileMapping.acquisition_id == acq.id).
                        all()
                    )
                    tpoints = np.unique(df.tpoint)
                    wavelengths = np.unique(df.wavelength)
                    bit_depth = np.unique(df.bit_depth)
                    if len(bit_depth) == 1:
                        bit_depth = bit_depth[0]
                    else:
                        raise MetadataError(
                            'Bit depth must be the same across experiment.'
                        )
                    for t in tpoints:
                        cycle = session.get_or_create(
                            tm.Cycle,
                            index=c_index, tpoint=t_index, plate_id=acq.plate.id
                        )

                        for w in wavelengths:
                            w_index = np.where(wavelengths == w)[0][0]
                            if is_multiplexing_experiment:
                                name = 'cycle-%d_wavelength-%s' % (c_index, w)
                            else:
                                name = 'wavelength-%s' % w
                            channel = session.get_or_create(
                                tm.Channel,
                                name=name, index=w_index, wavelength=w,
                                bit_depth=bit_depth,
                                experiment_id=acq.plate.experiment_id
                            )

                            image_file_mappings = session.query(
                                tm.ImageFileMapping
                                ).\
                                filter_by(
                                    tpoint=t, wavelength=w,
                                    acquisition_id=acq.id
                                )
                            for ifm in image_file_mappings:
                                ifm.tpoint = t_index
                                ifm.cycle_id = cycle.id
                                ifm.channel_id = channel.id

                        if is_time_series_experiment:
                            t_index += 1

                        c_index += 1
