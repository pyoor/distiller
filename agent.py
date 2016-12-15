#!/usr/bin/python
import sys

from client.tracer import TraceInserter
from client.minimizer import SeedMinimizer
from utils.config_import import DistillerConfig


def main(config_file):
    config = DistillerConfig(config_file, 'client')

    if "trace" in config.operations:
        tracer = TraceInserter(config)
        while tracer.ready():
            tracer.go()

    '''if "minimize" in config.operations:
        print "[ +D+ ] Checking for available minimization jobs."

        minimizer = SeedMinimizer(config_file)
        minimizer.wait()
        while minimizer.is_job_available():
            minimizer.go()
        else:
            print "[ +D+ ] No minimization jobs available."'''


def usage():
    print "Usage:", sys.argv[0], "<config.yml>"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        usage()
    else:
        main(sys.argv[1])
