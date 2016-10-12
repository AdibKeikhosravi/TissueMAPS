import time
import datetime
import logging
import gc3libs

import tmlib.models as tm
from tmlib.workflow.utils import get_task_data_from_sql_store
from tmlib.workflow.utils import print_task_status
from tmlib.workflow.utils import log_task_failure

logger = logging.getLogger(__name__)


class SubmissionManager(object):

    '''Mixin class for submission and monitoring of computational tasks.'''

    def __init__(self, experiment_id, program_name):
        '''
        Parameters
        ----------
        experiment_id: int
            ID of the processed experiment
        program_name: str
            name of the submitting program
        '''
        self.experiment_id = experiment_id
        self.program_name = program_name

    def register_submission(self, program_name=None):
        '''Generates a unique submission ID.

        Creates a database entry in the "submissions" table.

        Parameters
        ----------
        program_name: str, optional
            name of the submitting program (default: ``None``)

        Returns
        -------
        Tuple[int, str]
            ID of the submission and the name of the submitting user

        Warning
        -------
        Ensure that the "submissions" table get updated once the jobs
        were submitted, i.e. added to a running `GC3Pie` engine.
        To this end, use the :py:method:`tmlib.workflow.api.update_submission`
        method.

        See also
        --------
        :py:class:`tmlib.models.Submission`
        '''
        if program_name is None:
            program_name = self.program_name
        with tm.utils.MainSession() as session:
            submission = tm.Submission(
                experiment_id=self.experiment_id, program=program_name
            )
            session.add(submission)
            session.flush()
            return (submission.id, submission.experiment.user.name)

    def update_submission(self, jobs):
        '''Updates the submission with the submitted tasks.

        Sets the value for "top_task" column in the "submissions" table.

        Paramters
        ---------
        jobs: gc3libs.Task or gc3libs.workflow.TaskCollection
            submitted tasks

        See also
        --------
        :py:class:`tmlib.models.Submission`

        Raises
        ------
        AttributeError
            when `jobs` doesn't have a "persistent_id" attribute, which
            indicates that the task has not yet been inserted into the
            database table
        '''
        with tm.utils.MainSession() as session:
            submission = session.query(tm.Submission).get(jobs.submission_id)
            if not hasattr(jobs, 'persistent_id'):
                raise AttributeError(
                    'Task was not yet inserted into the database table.'
                )
            submission.top_task_id = jobs.persistent_id

    def get_task_id_of_last_submission(self):
        '''Gets the ID of the last submitted task for the given `experiment`
        and `program`.

        Returns
        -------
        int
            ID of top task that was last submitted
        '''
        with tm.utils.MainSession() as session:
            submission = session.query(tm.Submission).\
                filter_by(experiment_id=self.experiment_id, program=self.name).\
                order_by(tm.Submission.id.desc()).\
                first()
            return submission.top_task_id

    def submit_jobs(self, jobs, engine, start_index=0, monitoring_depth=1,
            monitoring_interval=10):
        '''Submits jobs to a cluster and continuously monitors their progress.

        Parameters
        ----------
        jobs: tmlib.tmaps.workflow.WorkflowStep
            jobs that should be submitted
        engine: gc3libs.core.Engine
            engine that should submit the jobs
        start_index: int, optional
            index of the job at which the collection should be (re)submitted
        monitoring_depth: int, optional
            recursion depth for job monitoring, i.e. in which detail subtasks
            in the task tree should be monitored (default: ``1``)
        monitoring_interval: int, optional
            seconds to wait between monitoring iterations (default: ``10``)

        Returns
        -------
        dict
            information about each job

        Warning
        -------
        This method is intended for interactive use via the command line only.
        '''
        logger.debug('monitoring depth: %d' % monitoring_depth)
        if monitoring_depth < 0:
            monitoring_depth = 0
        if monitoring_interval < 0:
            monitoring_interval = 0

        logger.debug('add jobs %s to engine', jobs)
        engine.add(jobs)
        engine.redo(jobs, start_index)

        # periodically check the status of submitted jobs
        t_submitted = datetime.datetime.now()

        break_next = False
        while True:

            time.sleep(monitoring_interval)
            logger.debug('wait for %d seconds', monitoring_interval)

            t_elapsed = datetime.datetime.now() - t_submitted
            logger.info('elapsed time: %s', str(t_elapsed))

            logger.info('progress...')
            engine.progress()

            status_data = get_task_data_from_sql_store(jobs, monitoring_depth)
            print_task_status(status_data)

            if break_next:
                break

            if (jobs.execution.state == gc3libs.Run.State.TERMINATED or
                    jobs.execution.state == gc3libs.Run.State.STOPPED):
                break_next = True
                engine.progress()  # one more iteration to update status_data

        status_data = get_task_data_from_sql_store(jobs)
        log_task_failure(status_data, logger)

        return status_data
