from . import logo
from . import __version__
from .api import IllumstatsCalculator
from ..cli import CommandLineInterface
from ..cycle import Cycle


class Corilla(CommandLineInterface):

    def __init__(self, args):
        super(Corilla, self).__init__(args)
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
        return IllumstatsCalculator(
                    cycle=cycle,
                    stats_file_format_string=self.cfg['STATS_FILE'],
                    prog_name=self.name)

    @staticmethod
    def call(args):
        '''
        Calls the method that matches the name of the specified subparser with
        the parsed command line arguments.

        Parameters
        ----------
        args: arparse.Namespace
            parsed command line arguments

        See also
        --------
        `tmt.corilla.argparser`_
        '''
        cli = Corilla(args)
        getattr(cli, args.subparser_name)()
