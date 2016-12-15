#!/usr/bin/python
import beanstalkc
import os
import sqlite3
import sys
import threading
from time import sleep

from server.inserter import Inserter
from server.minprocessor import MinProcessor
from server.preprocess import TraceProcessor
from server.reducer import TraceReducer
from utils.config_import import DistillerConfig


def prepare_db(db_path, action):
    if action == "R":
        os.remove(db_path)

    sql = sqlite3.connect(db_path)
    c = sql.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS modules (num INTEGER PRIMARY KEY, name TEXT, UNIQUE (name))''')
    c.execute('''CREATE TABLE IF NOT EXISTS key_lookup (seed_name TEXT PRIMARY KEY, ublock_cnt INT, traces BLOB)''')

    # Results are calculated using the full data set
    # Wipe if they exist
    c.execute('''DROP TABLE IF EXISTS results''')
    c.execute('''CREATE TABLE results (seed_name TEXT PRIMARY KEY, ublock_cnt INT)''')
    sql.commit()


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

        '''if "minimize" in config.operations:
            inserter = Inserter(config)
            t1 = threading.Thread(target=inserter.insert_mincase)
            t1.start()

            sleep(10)
            minprocessor = MinProcessor(config)
            t2 = threading.Thread(target=minprocessor.go)
            t2.start()

            t1.join()
            t2.join()'''

    finally:
        pass


def usage():
    print "Usage:", sys.argv[0], "<config.yml>"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        usage()
    else:
        main(sys.argv[1])
