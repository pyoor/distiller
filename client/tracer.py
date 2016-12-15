import beanstalkc
import os
import tempfile
from time import sleep

import runner
from common import packer


class TraceInserter:
    def __init__(self, config):
        self.bs = beanstalkc.Connection(config.host)
        self.d_path = config.drio_path
        self.t_path = config.target_path
        self.t_args = config.target_args
        self.w_time = config.w_time
        self.m_time = config.m_time
        self.project_name = config.project_name

        self.trace_queue = config.trace_queue
        self.trace_results = config.trace_results

        self.job = None
        self.s_name = None
        self.s_data = None
        self.s_path = None
        self.s_ext = None
        self.s_fd = None
        self.s_path = None

    def ready(self):
        self.bs.watch(self.trace_queue)
        self.job = self.bs.reserve(timeout=60)
        self.ignore(self.trace_queue)

        if self.job:
            return True
        else:
            print "[ +D+ ] No trace jobs available."
            return False

    def parse(self):
        body = packer.unpack(self.job.body)
        self.s_name = body['name']
        self.s_data = body['data']
        self.s_ext = os.path.splitext(self.s_name)[1]
        self.s_fd, self.s_path = tempfile.mkstemp(self.s_ext)

        # Write seed data to file
        with os.fdopen(self.s_fd, 'wb+') as seed_file:
            seed_file.write(self.s_data)

    def clean(self):
        while True:
            try:
                if os.path.isfile(self.s_path):
                    os.remove(self.s_path)
            except WindowsError:
                print "[ +E+ ] - Error deleting file."
                sleep(1)
            else:
                break

    def insert(self):
        for i in range(0, 3):
            try:
                print "[ +D+ ] - Attempting to trace %s" % self.s_name
                logfile = runner.run(self.d_path, self.t_path, self.t_args, self.s_name, self.s_path, self.w_time, self.m_time)

                if logfile is not None:
                    trace_data = {
                        'seed_name': self.s_name,
                        'data': logfile
                    }

                    trace = packer.pack(trace_data)
                    # Set long TTR as trace processing may take a while
                    self.bs.use(self.trace_results)
                    self.bs.put(trace, ttr=600)
                    self.job.delete()
                    break
                else:
                    print "[ +E+ ] - Error retrieving log file. Restarting."

            except Exception as e:
                print "[ +D+ ] - Something went wrong. Restarting."

        else:
            print "[ +E+ ] - Reached max tries.  Burying."
            self.job.bury()

    def go(self):
        """
        Get job and run trace.
        If successful, upload results, otherwise bury
        """
        self.parse()
        self.insert()
        self.clean()
