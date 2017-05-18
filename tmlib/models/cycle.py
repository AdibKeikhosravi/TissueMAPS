# TmLibrary - TissueMAPS library for distibuted image analysis routines.
# Copyright (C) 2016  Markus D. Herrmann, University of Zurich and Robin Hafen
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import os
import logging
from sqlalchemy import Column, Integer, BigInteger, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy import UniqueConstraint

from tmlib.models.base import ExperimentModel, DateMixIn

logger = logging.getLogger(__name__)


class Cycle(ExperimentModel, DateMixIn):

    '''A *cycle* represents an individual image acquisition time point.
    In case of a time series experiment, *cycles* have different time points,
    while in case of a "multiplexing" experiment, they have the same time point.

    Attributes
    ----------
    site_shifts: List[tmlib.models.site.SiteShift]
        shifts belonging to the cycle
    '''

    __tablename__ = 'cycles'

    __table_args__ = (UniqueConstraint('tpoint', 'index'), )

    #: int: zero-based index in the time series
    tpoint = Column(Integer, index=True)

    #: int: zero-based index in the acquisition sequence
    index = Column(Integer, index=True)

    #: int: ID of parent experiment
    experiment_id = Column(
        BigInteger,
        ForeignKey('experiment.id', onupdate='CASCADE', ondelete='CASCADE'),
        index=True
    )

    #: tmlib.models.experiment.Experiment: parent experiment
    experiment = relationship(
        'Experiment',
        backref=backref('cycles', cascade='all, delete-orphan')
    )

    def __init__(self, index, tpoint, experiment_id):
        '''
        Parameters
        ----------
        index: int
            index of the cycle (based on the order of acquisition)
        tpoint: int
            time point index
        experiment_id: int
            ID of the parent
            :class:`Experiment <tmlib.models.experiment.Experiment>`
        '''
        self.index = index
        self.tpoint = tpoint
        self.experiment_id = experiment_id

    def __repr__(self):
        return '<Cycle(id=%r, tpoint=%r)>' % (self.id, self.tpoint)
