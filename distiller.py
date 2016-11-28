#!/usr/bin/python
import beanstalkc
import os
import sqlite3
import sys
import threading
from time import sleep

from utils.config_import import read_config
from server.reducer import TraceReducer
from server.preprocess import TraceProcessor
from server.seed_inserter import SeedInserter


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


def verify_config(config_file):
    config = read_config(config_file, "server")

    try:
        if not config['operation']:
            print "You must specify at least a single operation type! Exiting."
            sys.exit()

        if not os.path.isdir(config['seed_path']):
            print "Could not locate seed_path! Exiting."
            sys.exit()

        if os.path.isfile(config['db_path']):
            action = None
            while action != "R" and action != "A":
                action = raw_input("Database Exists! [R]eplace or [A]ppend? ").upper()
        else:
            action = "N"

        prepare_db(config['db_path'], action)

        config['output_path'] = os.path.join(config['output_path'], config['project-name'])
        if not os.path.isdir(config['output_path']):
            os.makedirs(config['output_path'])

    except KeyError:
        raise Exception("Configuration file appears to have been corrupted!")

    return config


def main(config_file):
    try:
        config = verify_config(config_file)

        if "trace" in config['operation']:
            # Insert seeds into beanstalk
            inserter = SeedInserter(config)
            t1 = threading.Thread(target=inserter.go)
            t1.start()

            # Start trace preprocessor
            sleep(10)
            processor = TraceProcessor(config)
            t2 = threading.Thread(target=processor.go)
            t2.start()

            t1.join()
            t2.join()

        if "reduce" in config['operation']:
            reducer = TraceReducer(config)
            reducer.go()

        #if "minimize" in config['operation']:
        #    minimizer = SeedMinimizer(config)
        #    minimizer.go()

    finally:
        pass


def usage():
    print "Usage:", sys.argv[0], "<config.yml>"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        usage()
    else:
        main(sys.argv[1])
