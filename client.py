#!/usr/bin/python
import argparse
import os
import sys

from trace_inserter import TraceInserter

DYNAMO_PATH = "C:\\DynamoRIO\\bin32\\drrun.exe"
TARGET_PATH = 'C:\\Program Files\\Windows NT\\Accessories\\wordpad.exe'
TARGET_ARGS = ''
MAX_ATTEMPTS = 3
WAIT_TIME = 5


def main():
    parser = argparse.ArgumentParser(
        prog="client.py",
        usage="client.py --host 192.168.1.100 --port 11300",
    )
    parser.add_argument("-host", help="Beanstalkd address", required=True)
    parser.add_argument("-port", help="Beanstalkd port", default='11300', type=int)

    args = parser.parse_args()
    host = args.host
    port = args.port

    # Verify file locations
    if not os.path.isfile(DYNAMO_PATH):
        print "[ +E+ ] - Cannot find DynamoRIO.  Exiting!"
        sys.exit()

    if not os.path.isfile(TARGET_PATH):
        print "[ +E+ ] - Cannot find target binary.  Exiting!"
        sys.exit()

    # Start tracing
    tracer = TraceInserter(host, port, DYNAMO_PATH, TARGET_PATH, TARGET_ARGS, WAIT_TIME)
    while tracer.ready():
        tracer.go()
    else:
        print "[ +D+ ] No more seeds available.  Exiting!"

main()
