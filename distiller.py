#!/usr/bin/python
import beanstalkc
import sys
import threading
from time import sleep

from server.inserter import Inserter
from server.preprocess import TraceProcessor
from server.reducer import TraceReducer
from utils.config_import import DistillerConfig


def check_beanstalk():
    try:
        beanstalkc.Connection(host='127.0.0.1', port=11300)
    except beanstalkc.SocketError:
        print "Could not connect to beanstalkd!"
        sys.exit()


def main(config_file):
    try:
        config = DistillerConfig(config_file, 'server')

        if "trace" in config.operations:
            # Insert seeds into beanstalk
            inserter = Inserter(config)
            t1 = threading.Thread(target=inserter.insert_seed)
            t1.start()

            # Start trace preprocessor
            sleep(10)
            processor = TraceProcessor(config)
            t2 = threading.Thread(target=processor.go)
            t2.start()

            t1.join()
            t2.join()

        if "reduce" in config.operations:
            reducer = TraceReducer(config)
            reducer.go()

    finally:
        pass


def usage():
    print "Usage:", sys.argv[0], "<config.yml>"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        usage()
    else:
        main(sys.argv[1])
