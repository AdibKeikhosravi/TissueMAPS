import os
import logging
from sqlalchemy import Column, String, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgres import JSONB
from sqlalchemy.orm import relationship, backref
from sqlalchemy import UniqueConstraint

from tmlib.models import Model, DateMixIn
from tmlib.models import distribute_by
from tmlib.models.status import FileUploadStatus as fus
from tmlib.models.utils import remove_location_upon_delete
from tmlib.utils import autocreate_directory_property

logger = logging.getLogger(__name__)

#: Format string for acquisition locations
ACQUISITION_LOCATION_FORMAT = 'acquisition_{id}'


@remove_location_upon_delete
@distribute_by('id')
class Acquisition(Model, DateMixIn):

    '''An *acquisition* contains all files belonging to one microscope image
    acquisition process. Note that in contrast to a *cycle*, an *acquisition*
    may contain more than one time point.

    The incentive to grouped files this way relates to the fact that most
    microscopes generate separate metadata files for each *acquisition*.

    Attributes
    ----------
    name: str
        name of the acquisition
    description: str
        description of the acquisition
    status: str
        processing status
    plate_id: int
        ID of the parent plate
    plate: tmlib.models.Plate
        parent plate to which the acquisition belongs
    microscope_image_files: List[tmlib.models.MicroscopeImageFile]
        image files generated by the microscope
    microscope_metadata_files: List[tmlib.models.MicroscopeMetadataFile]
        metadata files generated by the microscope
    ome_xml_files: List[tmlib.models.OmeXmlFile]
        OMEXML files extracted from microscope image files
    image_file_mappings: List[tmlib.models.ImageFileMapping]
        maps pixel planes to microscope image files
    '''

    #: str: name of the corresponding database table
    __tablename__ = 'acquisitions'

    __table_args__ = (UniqueConstraint('name', 'plate_id'), )

    # Table columns
    name = Column(String, index=True)
    description = Column(Text)
    plate_id = Column(
        Integer,
        ForeignKey('plates.id', onupdate='CASCADE', ondelete='CASCADE')
    )

    # Relationships to other tables
    plate = relationship(
        'Plate',
        backref=backref('acquisitions', cascade='all, delete-orphan')
    )

    def __init__(self, name, plate_id, description=''):
        '''
        Parameters
        ----------
        name: str
            name of the acquisition
        plate_id: int
            ID of the parent plate
        description: str, optional
            description of the acquisition
        '''
        # TODO: ensure that name is unique within plate
        self.name = name
        self.description = description
        self.plate_id = plate_id

    @autocreate_directory_property
    def location(self):
        '''str: location were the acquisition content is stored'''
        if self.id is None:
            raise AttributeError(
                'Acquisition "%s" doesn\'t have an entry in the database yet. '
                'Therefore, its location cannot be determined.' % self.name
            )
        return os.path.join(
            self.plate.acquisitions_location,
            ACQUISITION_LOCATION_FORMAT.format(id=self.id)
        )

    @autocreate_directory_property
    def microscope_images_location(self):
        '''str: location where microscope image files are stored'''
        return os.path.join(self.location, 'microscope_images')

    @autocreate_directory_property
    def microscope_metadata_location(self):
        '''str: location where microscope metadata files are stored'''
        return os.path.join(self.location, 'microscope_metadata')

    @autocreate_directory_property
    def omexml_location(self):
        '''str: location where extracted OMEXML files are stored'''
        return os.path.join(self.location, 'omexml')

    @property
    def status(self):
        '''str: upload status based on the status of microscope files'''
        child_status = set([
            f.upload_status for f in self.microscope_image_files
        ]).union(set([
            f.upload_status for f in self.microscope_metadata_files
        ]))
        if fus.UPLOADING in child_status:
            return fus.UPLOADING
        elif len(child_status) == 1 and fus.COMPLETE in child_status:
            return fus.COMPLETE
        else:
            return fus.WAITING

    def as_dict(self):
        '''Returns attributes as key-value pairs.

        Returns
        -------
        dict
        '''
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'status': self.status
        }

    def belongs_to(self, user):
        '''Determines whether the acquisition belongs to a given `user`.

        Parameters
        ----------
        user: tmlib.user.User
            `TissueMAPS` user

        Returns
        -------
        bool
            whether acquisition belongs to `user`
        '''
        return self.plate.belongs_to(user)

    def __repr__(self):
        return '<Acquisition(id=%r, name=%r)>' % (self.id, self.name)


@distribute_by('id')
class ImageFileMapping(Model):

    '''A mapping of an individual 2D pixels plane (a future channel image file)
    to its location within one or more microscope image files defined
    according to the
    `OME data model <http://www.openmicroscopy.org/site/support/ome-model/>`_.

    See also
    --------
    :py:class:`tmlib.models.MicroscopeImageFile`
    :py:class:`tmlib.models.ChannelImageFile`

    Attributes
    ----------
    tpoint: int
        zero-based time point index in the time series
    wavelength: str
        name of the wavelength
    bit_depth: int
        number of bites used to indicate intensity
    map: dict
        maps an individual pixels plane to location(s) within microscope
        image files
    acquisition_id: int
        ID of the parent acquisition
    acquisition: tmlib.models.Acquisition
        parent acquisition to which the image file mapping belongs
    site_id: int
        ID of the parent site
    site: tmlib.models.Site
        parent site to which the image file mapping belongs
    cycle_id: int
        ID of the parent cycle
    cycle: tmlib.models.Cycle
        parent cycle to which the image file mapping belongs
    channel_id: int
        ID of the parent channel
    channel: tmlib.models.Channel
        parent channel to which the image file mapping belongs
    '''

    __tablename__ = 'image_file_mappings'

    __table_args__ = (
        UniqueConstraint(
            'tpoint', 'site_id', 'cycle_id', 'wavelength'
        ),
    )

    tpoint = Column(Integer, index=True)
    bit_depth = Column(Integer)
    wavelength = Column(String, index=True)
    map = Column(JSONB)
    site_id = Column(
        Integer,
        ForeignKey('sites.id', onupdate='CASCADE', ondelete='CASCADE')
    )
    cycle_id = Column(
        Integer,
        ForeignKey('cycles.id', onupdate='CASCADE', ondelete='CASCADE')
    )
    acquisition_id = Column(
        Integer,
        ForeignKey('acquisitions.id', onupdate='CASCADE', ondelete='CASCADE')
    )
    channel_id = Column(
        Integer,
        ForeignKey('channels.id', onupdate='CASCADE', ondelete='CASCADE')
    )

    # Relationships to other tables
    site = relationship(
        'Site',
        backref=backref('image_file_mappings', cascade='all, delete-orphan')
    )
    acquisition = relationship(
        'Acquisition',
        backref=backref('image_file_mappings', cascade='all, delete-orphan')
    )
    cycle = relationship(
        'Cycle',
        backref=backref('image_file_mappings', cascade='all, delete-orphan')
    )
    channel = relationship(
        'Channel',
        backref=backref('image_file_mappings', cascade='all, delete-orphan')
    )

    def __init__(self, tpoint, wavelength, bit_depth, map, site_id,
                 acquisition_id, cycle_id=None, channel_id=None):
        '''
        Parameters
        ----------
        tpoint: int
            zero-based time point index in the time series
        wavelength: str
            name of the wavelength
        bit_depth: int
            number of bites used to indicate intensity
        map: dict
            maps an individual pixels plane to location(s) within microscope
            image files
        site_id: int
            ID of the parent site
        acquisition_id: int
            ID of the parent acquisition
        cycle_id: int, optional
            ID of the parent cycle (default: ``None``)
        channel_id: int, optional
            ID of the parent channel (default: ``None``)
        '''
        self.tpoint = tpoint
        self.wavelength = wavelength
        self.bit_depth = bit_depth
        self.map = map
        self.site_id = site_id
        self.acquisition_id = acquisition_id
        self.cycle_id = cycle_id
        self.channel_id = channel_id
