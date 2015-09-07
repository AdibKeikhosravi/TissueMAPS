import re
import os
from natsort import natsorted
from . import utils
from .plates import WellPlate
from .plates import Slide


class Experiment(object):
    '''
    Class for an experiment.

    An *experiment* represents a folder on disk that contains image files
    and additional data associated with the images, such as metainformation,
    measured features, segmentations, etc. The structure of the directory tree
    and the location of files is defined via format strings
    in the configuration settings file.

    An experiment consists of one or more *cycles*. A *cycle* represents a
    particular time point of image acquisition for a given sample.
    In the simplest case, the experiment represents a *cycle* itself, i.e. a
    single round of image acquisition. However, the experiment may also
    represent a time series, consisting of several iterative rounds of
    image acquisitions. In this case each *cycle* should be represented by a
    separate subfolder on disk. The names of these folders should encode the
    name of the experiment as well as the *cycle* identifier number,
    i.e. the one-based index of the time series sequence.
    For example, given an experiment called "myExperiment",
    the directory tree could be structured as follows::

        myExperiment           # experiment folder
            myExperiment-1     # subexperiment folder of cycle #1
            myExperiment-2     # subexperiment folder of cycle #2
            ...

    See also
    --------
    `cycle.Cycle`_
    `tmt.cfg`_
    `user.cfg`_
    '''

    def __init__(self, experiment_dir, cfg):
        '''
        Initialize an instance of class Experiment.

        Parameters
        ----------
        experiment_dir: str
            absolute path to experiment folder
        cfg: dict
            configuration settings
        '''
        self.experiment_dir = os.path.abspath(experiment_dir)
        self.cfg = cfg

    @property
    def user_cfg_file(self):
        '''
        Returns
        -------
        str
            absolute path to experiment-specific user configuration file
        '''
        self._user_cfg_file = self.cfg['USER_CFG_FILE'].format(
                                            experiment_dir=self.dir,
                                            experiment=self.name,
                                            sep=os.path.sep)
        return self._user_cfg_file

    @property
    def user_cfg(self):
        '''
        Returns
        -------
        dict
            experiment-specific configuration settings provided by the user
        '''
        # TODO: shall we do this via the database instead?
        self._user_cfg = utils.read_yaml(self.user_cfg_file)
        return self._user_cfg

    @property
    def name(self):
        '''
        Returns
        -------
        str
            name of the experiment
        '''
        self._name = os.path.basename(self.experiment_dir)
        return self._name

    @property
    def dir(self):
        '''
        Returns
        -------
        str
            absolute path to the experiment directory
        '''
        return self.experiment_dir

    def _is_cycle(self, folder):
        regexp = utils.regex_from_format_string(self.cfg['CYCLE_DIR'])
        return True if re.match(regexp, folder) else False

    @property
    def cycles(self):
        '''
        Returns
        -------
        List[WellPlate or Slide]
            cycle objects

        See also
        --------
        `plates.WellPlate`_
        `plates.Slide`_
        `tmt.cfg`_
        '''
        cycle_dirs = [os.path.join(self.dir, f) for f in os.listdir(self.dir)
                      if os.path.isdir(os.path.join(self.dir, f))
                      and self._is_cycle(f)]
        cycle_dirs = natsorted(cycle_dirs)
        if not cycle_dirs:
            # in this case, the *cycle* directory is the same as the
            # the experiment directory
            cycle_dirs = self.experiment_dir
        if self.user_cfg['WELLPLATE_FORMAT']:
            plate_format = self.user_cfg['NUMBER_OF_WELLS']
            cycles = [WellPlate(c, self.cfg, plate_format) for c in cycle_dirs]
        else:
            cycles = [Slide(c, self.cfg) for c in cycle_dirs]
        self._cycles = cycles
        return self._cycles

    @property
    def reference_cycle(self):
        '''
        Returns
        -------
        str
            name of the reference cycle
        '''
        return self.cfg['REFERENCE_CYCLE']

    @property
    def data_file(self):
        '''
        Returns
        -------
        str
            absolute path to the HDF5 file holding the measurements dataset

        See also
        --------
        `dafu`_
        '''
        self._data_filename = self.cfg['DATA_FILE'].format(
                                            experiment_dir=self.experiment_dir,
                                            sep=os.path.sep)
        return self._data_filename

    @property
    def layers_dir(self):
        '''
        Returns
        -------
        str
            absolute path to the folder holding the layers (image pyramids)
        '''
        self._layers_dir = self.cfg['LAYERS_DIR'].format(
                                            experiment_dir=self.experiment_dir,
                                            sep=os.path.sep)
        return self._layers_dir

    @property
    def registration_dir(self):
        '''
        Returns
        -------
        str
            absolute path to the folder holding the calculated shift values
            of the image registration step
        '''
        self._registration_dir = self.cfg['REGISTRATION_DIR'].format(
                                            experiment_dir=self.experiment_dir,
                                            sep=os.path.sep)
        return self._registration_dir
