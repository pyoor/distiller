import beanstalkc
import msgpack
import os
import tempfile
from time import sleep
import zlib
from trace_runner import TraceRunner


class TraceInserter:
    def __init__(self, host, drio_path, target_path, target_args, wait_time, max_timeout):
        self.bs = beanstalkc.Connection(host)
        self.d_path = drio_path
        self.t_path = target_path
        self.t_args = target_args
        self.w_time = wait_time
        self.max_timeout = max_timeout

        self.job = None
        self.s_name = None
        self.s_data = None
        self.s_path = None
        self.s_ext = None
        self.s_fd = None
        self.s_path = None

    def ready(self):
        self.bs.watch('seeds')
        self.job = self.bs.reserve(timeout=60)
        self.bs.ignore('seeds')

        if self.job:
            return True
        else:
            return False

    def parse(self):
        body = msgpack.unpackb(self.job.body)
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
                runner = TraceRunner(self.d_path, self.t_path, self.t_args, self.s_name, self.s_path, self.w_time, self.max_timeout)

                # Run trace
                runner.go()

                # Sleep 2s before checking log file
                sleep(2)
                if runner.log:
                    trace_data = {
                        'seed_name': self.s_name,
                        'data': runner.log
                    }

                    trace = zlib.compress(msgpack.packb(trace_data, use_bin_type=True))
                    # Set long TTR as trace processing may take a while
                    self.bs.use('reduction-results')
                    self.bs.put(trace, ttr=600)
                    self.job.delete()
                    break
                else:
                    print "[ +E+ ] - Error retrieving log file. Restarting."

            except Exception:
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
