#!/usr/bin/python
import argparse
import os
import psutil
import shlex
import shutil
import subprocess
import sys
import time
from glob import glob

import beanstalkc
import msgpack

LOG_DIR = 'minlog'
LOG_PATH = os.path.join(os.getcwd(), LOG_DIR)
DYNAMO_PATH = 'C:/DynamoRIO5/bin32/drrun.exe'

# These are case sensitive!
TARGET_PATH = 'C:\Program Files\Windows NT\Accessories\wordpad.exe'
TARGET_NAME = 'wordpad.exe'


def init():
    try:
        if not os.path.isdir(LOG_PATH):
            os.makedirs(LOG_PATH)
        else:
            print "[ +D+ ] - Log directory exists!"
            choice = raw_input('[ +D+ ] - Do you want to remove it? (Y/n): ').lower()
            if choice in ("Y", "y", ''):
                shutil.rmtree(LOG_PATH, ignore_errors=True)
                os.makedirs(LOG_PATH)
            else:
                sys.exit()
    except:
        raise


def kill_stale_processes():
    while True:
        stale_processes = []
        for proc in psutil.process_iter():
            if proc.name() == TARGET_NAME:
                stale_processes.append(proc.pid)

        if len(stale_processes) == 0:
            break
        else:
            print "[ +D+ ] - Stale processes found!  Attempting to kill"
            for p in stale_processes:
                psutil.Process(p).kill()


def trace_seed(bs_conn):
    try:
        # Get job
        if 'seed_tube' in bs_conn.tubes():
            bs_conn.watch('seed_tube')
            job = bs_conn.reserve()

            # Parse job data
            seed_name, seed_data = msgpack.unpackb(job.body)
            seed_path = os.path.join(os.getcwd(), seed_name)

            # Write seed data to file
            seed_file = open(seed_path, 'wb+')
            seed_file.write(seed_data)
            seed_file.close()

            # Kill stale processes
            kill_stale_processes()

            # Launch drcov
            print "[ +D+ ] - Tracing seed: %s" % seed_name
            command = [DYNAMO_PATH, '-t', 'drcov', '-dump_text', '-logdir', 'minlog', '--', TARGET_PATH, seed_path]
            p = subprocess.Popen(command)

            # Wait 5s before checking process state
            time.sleep(5)
            if psutil.Process(p.pid).children():
                for child in psutil.Process(p.pid).children():
                    if child.name() == TARGET_NAME:
                        while True:
                            cpu = all(0 == child.cpu_percent(interval=0.1) for x in xrange(8))
                            if cpu is not None and cpu is True:
                                null = open(os.devnull, 'w')
                                command = "taskkill /PID %s " % child.pid
                                subprocess.call(shlex.split(command), stdout=null, stderr=subprocess.STDOUT)
                                print "[ +D+ ] - Send termination signal to: %s" % child.pid

                                time.sleep(4)
                                if child.is_running():
                                    print "[ +D+ ] - Child still running.  Trying again more forcefully."
                                    print "[ +D+ ] - This will likely prevent the log file from being created."
                                    command = "taskkill /F /PID %s " % child.pid
                                    subprocess.call(shlex.split(command), stdout=FNULL, stderr=subprocess.STDOUT)
                                break
                    else:
                        print "[ +D+ ] - Something went wrong."
                        print "[ +D+ ] - Child name does not match target selection."
                        job.release()

            # Sleep 2s before checking log entries
            time.sleep(2)

            # Get log file.  There should only be one
            log_entries = glob(os.path.join(LOG_PATH, '*.log'))
            if len(log_entries) != 1:
                print "[ +D+ ] - More than 1 log file found. Restarting."
                shutil.rmtree(LOG_PATH, ignore_errors=True)
                os.makedirs(LOG_PATH)
                job.release()
                return False
            else:
                trace_path = log_entries[0]

            with open(trace_path, 'r') as d:
                trace_data = d.read()

            if len(trace_data) == 0:
                print "[ +D+ ] - Trace file is empty. Restarting."
                job.release()
                return False

            trace = msgpack.packb({'seed_name': seed_name, 'data': trace_data}, use_bin_type=True)
            bs_conn.use('results_tube')

            # Set long TTR as trace processing may take a while
            bs_conn.put(trace, ttr=3600)
            job.delete()
            os.remove(trace_path)
            os.remove(seed_path)
    except:
        print "[ +D+ ] - Something went wrong. Restarting."
        job.release()
        return False


def cleanup():
    try:
        if os.path.isdir(LOG_PATH):
            shutil.rmtree(LOG_PATH, ignore_errors=True)
    except:
        raise


def main():
    try:
        parser = argparse.ArgumentParser(
            prog="client.py",
            usage="client.py --host 192.168.1.100 --port 11300",
        )
        parser.add_argument("--host", help="Path to seeds directory", required=True)
        parser.add_argument("--port", help="Path to trace database", default='11300', type=int)

        args = parser.parse_args()
        if args.host:
            bs_host = args.host
        if args.port:
            bs_port = args.port

        init()

        # Connect
        try:
            bs_conn = beanstalkc.Connection(host=bs_host, port=bs_port, connect_timeout=30)

            while 'seed_tube' in bs_conn.tubes() and bs_conn.stats_tube('seed_tube')['current-jobs-ready'] > 0:
                trace_seed(bs_conn)
            else:
                print "[ +D+ ] No more seeds available.  Exiting!"
        except beanstalkc.SocketError:
            print "[ +E+ ] - Could not connect to host.  Exiting!"

    finally:
        cleanup()


main()
