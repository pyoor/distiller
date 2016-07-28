import os
import glob
import shlex
import psutil
import shutil
import tempfile
import subprocess
from time import sleep, time


class TraceRunner:
    def __init__(self, dynamo_path, target_path, target_args, seed_name, seed_path, wait_time, max_timeout):
        self.d_path = dynamo_path
        self.t_path = target_path
        self.t_args = target_args
        self.s_name = seed_name
        self.s_path = seed_path
        self.wait = wait_time
        self.max_timeout = max_timeout

        self.t_name = os.path.basename(target_path)
        self.l_path = tempfile.mkdtemp()
        self.null = open(os.devnull, 'w')

        self.start_time = None

        self.proc = None
        self.ppid = None

        self.log = None

    def go(self):
        self.run()
        self.clean()

    def run(self):
        """
        Instrument target process with seed
        """
        print "[ +D+ ] - Tracing seed: %s" % os.path.basename(self.s_name)
        command = [self.d_path, '-t', 'drcov', '-dump_text', '-logdir', self.l_path, '--', self.t_path, self.t_args, self.s_path]
        self.proc = subprocess.Popen(command, stdout=self.null, stderr=subprocess.STDOUT)

        self.start_time = time()

        sleep(self.wait)
        self.check()

    def check(self):
        """
        Check CPU usage of target process
        """
        try:
            self.ppid = self.proc.pid
            if psutil.Process(self.ppid).children():
                for child in psutil.Process(self.ppid).children():
                    if child.name() == self.t_name:
                        while True:
                            cpu = all(0 == child.cpu_percent(interval=0.1) for x in xrange(8))
                            if cpu is not None and cpu is True:
                                self.kill(child.pid)
                                break
                            end_time = time()
                            elapsed = end_time - self.start_time
                            if elapsed > self.max_timeout:
                                self.kill(child.pid)
                                break
        except psutil.NoSuchProcess:
            pass

    def kill(self, pid):
        """
        Attempt to kill nicely, else kill forcefully
        """
        for i in range(0, 20):
            if self.proc.poll() is None:
                try:
                    command = "taskkill /PID %s /T" % pid
                    subprocess.call(shlex.split(command), stdout=self.null, stderr=subprocess.STDOUT)
                except:
                    print "[ +E+ ] - Error killing process."
                    sleep(0.5)
            else:
                break

        # If process is still running, kill it forcefully
        sleep(2)
        if self.proc.poll() is None:
            command = "taskkill /F /PID %s /T" % pid
            subprocess.call(shlex.split(command), stdout=self.null, stderr=subprocess.STDOUT)

    def clean(self):
        """
        Save log and wipe dir before next run
        """
        sleep(3)
        log_entries = glob.glob(os.path.join(self.l_path, '*.log'))
        if len(log_entries) == 1 and os.path.getsize(log_entries[0]):
            with open(log_entries[0]) as f:
                self.log = f.read()
            shutil.rmtree(self.l_path, ignore_errors=True)
        else:
            self.log = None
