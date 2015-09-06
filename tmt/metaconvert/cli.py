from . import logo
from . import __version__
from .api import MetadataConverter
from ..cli import CommandLineInterface
from ..cycle import Cycle


class MetaConvert(CommandLineInterface):

    '''
    Command line interface for metadata conversion.
    '''

    def __init__(self, args):
        '''
        Initialize an instance of class MetaConvert.

        Parameters
        ----------
        args: arparse.Namespace
            parsed command line arguments
        '''
        super(MetaConvert, self).__init__(args)
        self.args = args

    @staticmethod
    def print_logo():
        print logo % {'version': __version__}

    @property
    def name(self):
        '''
        Returns
        -------
        str
            name of the program
        '''
        return self.__class__.__name__.lower()

    @property
    def _api_instance(self):
        cycle = Cycle(self.args.cycle_dir, self.cfg)
        return MetadataConverter(
                    cycle=cycle,
                    file_format=self.args.format,
                    image_file_format_string=self.cfg['IMAGE_FILE'],
                    prog_name=self.name)

    @staticmethod
    def call(args):
        '''
        Initializes an instance of class MetaConvert and calls the method
        that matches the name of the subparser with the parsed command
        line arguments.

        Parameters
        ----------
        args: arparse.Namespace
            parsed command line arguments
        '''
        cli = MetaConvert(args)
        getattr(cli, args.subparser_name)()
