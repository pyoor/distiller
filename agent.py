#!/usr/bin/python
import os
import sys

from utils.config_import import read_config
from client.trace_inserter import TraceInserter


def main(config_file):
    cfg = read_config(config_file, 'client')

    host = cfg['host']
    d_path = cfg['drio_path']
    t_path = cfg['target_path']
    t_args = cfg['target_args']
    w_time = cfg['wait_time']
    m_time = cfg['max_timeout']

    # Verify file locations
    if not os.path.isfile(d_path):
        print "[ +E+ ] - Cannot find DynamoRIO.  Exiting!"
        sys.exit()

    if not os.path.isfile(t_path):
        print "[ +E+ ] - Cannot find target binary.  Exiting!"
        sys.exit()

    # Start tracing
    tracer = TraceInserter(host, d_path, t_path, t_args, w_time, m_time)
    while tracer.ready():
        tracer.go()
    else:
        print "[ +D+ ] No more seeds available.  Exiting!"


def usage():
    print "Usage:", sys.argv[0], "<config.yml>"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        usage()
    else:
        main(sys.argv[1])
