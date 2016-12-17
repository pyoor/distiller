import os
import psutil
import shlex
import shutil
import subprocess
import tempfile
from glob import glob
from time import sleep, time


def run(dynamo_path, target_path, target_args, seed_path, wait_time, max_timeout):
    """
    Instrument target process with seed
    """
    log_path = tempfile.mkdtemp()
    devnull = open(os.devnull, 'w')
    command = [dynamo_path, '-t', 'drcov', '-dump_text', '-logdir', log_path, '--', target_path, target_args, seed_path]
    proc = subprocess.Popen(command, stdout=devnull, stderr=subprocess.STDOUT)

    sleep(wait_time)

    # Check process and kill when ready
    target_name = os.path.basename(target_path)
    check(proc, target_name, max_timeout)

    # Retrieve log file and clean remaining files
    logfile = clean(log_path)

    return logfile


def check(proc, target_name, max_timeout):
    """
    Check CPU usage of target process
    """
    try:
        pid = proc.pid
        start_time = time()
        if psutil.Process(pid).children():
            for child in psutil.Process(pid).children():
                if child.name() == target_name:
                    while True:
                        cpu = all(0 == child.cpu_percent(interval=0.1) for x in xrange(8))
                        if cpu is not None and cpu is True:
                            kill(proc, child.pid)
                            break
                        if max_timeout is not None or max_timeout != 0:
                            end_time = time()
                            elapsed = end_time - start_time
                            if elapsed > max_timeout:
                                kill(proc, child.pid)
                                break
    except psutil.NoSuchProcess:
        pass


def kill(proc, pid):
    """
    Attempt to kill nicely, else kill forcefully
    """
    devnull = open(os.devnull, 'w')
    for i in range(0, 20):
        if proc.poll() is None:
            try:
                command = "taskkill /PID %s /T" % pid
                subprocess.call(shlex.split(command), stdout=devnull, stderr=subprocess.STDOUT)
            except:
                print "[ +E+ ] - Error killing process."
                sleep(0.5)
        else:
            break

    # If process is still running, kill it forcefully
    sleep(2)
    if proc.poll() is None:
        command = "taskkill /F /PID %s /T" % pid
        subprocess.call(shlex.split(command), stdout=devnull, stderr=subprocess.STDOUT)


def clean(log_path):
    """
    Save log and wipe dir before next run
    """
    sleep(3)
    log_entries = glob(os.path.join(log_path, '*.log'))
    if len(log_entries) == 1 and os.path.getsize(log_entries[0]):
        with open(log_entries[0]) as f:
            logfile = f.read()
        shutil.rmtree(log_path, ignore_errors=True)
    else:
        logfile = None

    return logfile
