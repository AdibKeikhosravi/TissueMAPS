import os
import re
import shutil
from glob import glob
from natsort import natsorted
from ..cluster import ClusterRoutines


class MetadataExtractor(ClusterRoutines):

    '''
    Class for extraction of metadata from microscopic image files using the
    Bio-Formats command line tool
    `showinf <http://www.openmicroscopy.org/site/support/bio-formats5.1/users/comlinetools/display.html>`_.

    Upon extraction, the metadata is formatted according to the
    `Open Microscopy Environment (OME) schema <http://www.openmicroscopy.org/Schemas/Documentation/Generated/OME-2015-01/ome.html>`_
    and written to XML files.
    '''

    def __init__(self, experiment, prog_name, verbosity):
        '''
        Initialize an instance of class MetadataExtractor.

        Parameters
        ----------
        experiment: Experiment
            configured experiment object
        prog_name: str
            name of the corresponding program (command line interface)
        verbosity: int
            logging level

        See also
        --------
        `tmlib.cfg`_
        '''
        super(MetadataExtractor, self).__init__(
                experiment, prog_name, verbosity)
        self.experiment = experiment
        self.prog_name = prog_name
        self.verbosity = verbosity

    @staticmethod
    def _get_ome_xml_filename(image_filename):
        return re.sub(r'(%s)$' % os.path.splitext(image_filename)[1],
                      '.ome.xml', image_filename)

    def create_job_descriptions(self, **kwargs):
        '''
        Create job descriptions for parallel computing.

        Parameters
        ----------
        cfg_file: str
            absolute path to custom configuration file
        **kwargs: dict
            empty - no additional arguments

        Returns
        -------
        Dict[str, List[dict] or dict]
            job descriptions
        '''
        joblist = dict()
        joblist['run'] = list()
        output_files = list()
        count = 0
        for upload in self.experiment.uploads:
            for subupload in upload.subuploads:
                output_files.extend([
                    os.path.join(subupload.omexml_dir,
                                 self._get_ome_xml_filename(f))
                    for f in subupload.image_files
                ])

                for j in xrange(len(subupload.image_files)):
                    count += 1
                    joblist['run'].append({
                        'id': count,
                        'inputs': {
                            'image_files': [
                                os.path.join(subupload.image_dir,
                                             subupload.image_files[j])
                            ]
                        },
                        'outputs': {
                        }
                    })

            joblist['collect'] = {
                'inputs': {},
                'outputs': {
                    'omexml_files': output_files
                }
            }
        return joblist

    def _build_run_command(self, batch):
        input_filename = batch['inputs']['image_files'][0]
        command = [
            'showinf', '-omexml-only', '-nopix', '-novalid', '-no-upgrade',
            input_filename
        ]
        return command

    def run_job(self, batch):
        # Java job
        raise AttributeError('"%s" step has no "run" routine'
                             % self.prog_name)

    def _build_collect_command(self):
        command = [self.prog_name]
        command.extend(['-v' for x in xrange(self.verbosity)])
        command.append(self.experiment.dir)
        command.extend(['collect'])
        return command

    def collect_job_output(self, batch):
        '''
        The *showinf* command prints the OME-XML string to standard output.
        GC3Pie redirects the standard output to a log file. Here we copy the
        content of the log file to the files specified by the `omexml_files`
        attribute.

        The extracted metadata is used to create custom metadata, which will be
        subsequently used by TissueMAPS.

        Parameters
        ----------
        batch: dict
            description of the *collect* job
        **kwargs: dict
            additional variable input arguments as key-value pairs
        '''
        for i, f in enumerate(batch['outputs']['omexml_files']):
            output_files = glob(os.path.join(
                                self.log_dir, '*_%.5d*.out' % (i+1)))
            # Take the most recent one, in case there are outputs of previous
            # submissions
            output_files = natsorted(output_files)
            shutil.copyfile(output_files[0], f)

    def apply_statistics(self, joblist, wells, sites, channels, output_dir,
                         **kwargs):
        raise AttributeError('"%s" object doesn\'t have a "apply_statistics"'
                             ' method' % self.__class__.__name__)
