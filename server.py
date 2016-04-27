#!/usr/bin/python

import argparse
import beanstalkc
import os
import sqlite3
import sys
import threading
from time import sleep

from minimize import TraceMinimizer
from preprocess import TraceProcessor
from seed_inserter import SeedInserter


def prepare_db(db_path, action):
    if action == "replace":
        os.remove(db_path)

    sql = sqlite3.connect(db_path)
    c = sql.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS modules (num INTEGER PRIMARY KEY, name TEXT, UNIQUE (name))''')
    c.execute('''CREATE TABLE IF NOT EXISTS key_lookup (seed_name TEXT PRIMARY KEY, block_count INT, traces BLOB)''')

    # Results are calculated using the full data set
    # Wipe if they exist
    c.execute('''DROP TABLE IF EXISTS results''')
    c.execute('''CREATE TABLE results (seed_name TEXT PRIMARY KEY, block_count INT)''')
    sql.commit()


def check_bs():
    try:
        beanstalkc.Connection(host='127.0.0.1', port=11300)
    except beanstalkc.SocketError:
        print "Could not connect to beanstalkd!"
        sys.exit()


def main():
    try:
        parser = argparse.ArgumentParser(
            usage=argparse.SUPPRESS,
            formatter_class=argparse.RawTextHelpFormatter,
            description='''\

=================================================================================
Minimizer - Tool for performing corpus distillation.
=================================================================================

Available Modes:
    Trace - Distribute seeds to nodes for tracing
    Minimize - Minimize trace results

Usage:
    Perform trace and minimize
    Ex. server.py -trace -minimize -s ./seeds -d backup.db

    Add traces to an existing set
    Ex. server.py -trace -minimize -s ./seeds -d backup.db --append

    Replace existing results
    Ex. server.py -trace -minimize -s ./seeds -d backup.db --replace
            '''
        )

        parser.add_argument("-trace", help="Trace seeds", action="store_true")
        parser.add_argument("-minimize", help="Minimize traces", action="store_true")
        parser.add_argument("-d", help="Path to trace database", required=True, metavar='./backup.db')
        parser.add_argument("-s", help="Path to seeds directory", metavar='./seeds')
        parser.add_argument("-o", help="Path to save results", metavar='./output.csv')

        parser.add_argument("--append", help=argparse.SUPPRESS, action="store_true")
        parser.add_argument("--replace", help=argparse.SUPPRESS, action="store_true")
        parser.add_argument("--whitelist",
                            help="Comma separated list of allowed modules.\nEx: ntdll.dll,msvcrt.dll", metavar="")
        parser.add_argument("--blacklist",
                            help="Comma separated list of blocked modules.\nEx: ntdll.dll,msvcrt.dll", metavar="")

        if len(sys.argv[1:]) == 0:
            parser.print_help()
            parser.exit()

        args = parser.parse_args()
        if not (args.trace or args.minimize):
            parser.error("No action specified.  You must specify -trace, -minimize, or both!")

        print args.d
        if args.d:
            db_path = args.d
            action = "new"
            if os.path.isfile(db_path):
                if args.replace and args.append:
                    parser.error("Conflicting arguments.  You must specify --append OR --replace!")
                elif not args.replace and not args.append:
                    parser.error("Database exists.  You must specify --append or --replace!")

                if args.replace:
                    action = "replace"
                elif args.append:
                    action = "append"

            prepare_db(db_path, action)

        if args.o:
            out_file = args.o
            if os.path.isfile(out_file):
                parser.error("Results file exists!  Please specify a new filename.")
        if args.s:
            seed_dir = args.s
            if not os.path.isdir(seed_dir):
                parser.error("Can't find seed directory.  Confirm the path is correct.")

        do_trace = True if args.trace else False
        if args.minimize:
            do_minimize = True
            if not args.o:
                parser.error("argument --out is required")
        else:
            do_minimize = False

        # Parse whitelist options
        wl = args.whitelist.split(',') if args.whitelist else False

        # Add these default blacklist modules
        bl = ['<unknown>', 'dynamorio.dll', 'drcov.dll']
        if args.blacklist:
            bl.extend(args.blacklist.split(','))

        if do_trace:
            # Insert seeds into beanstalk
            inserter = SeedInserter(db_path, seed_dir)
            t1 = threading.Thread(target=inserter.go)
            t1.start()

            # Start trace preprocessor
            sleep(10)
            processor = TraceProcessor(db_path, wl, bl)
            t2 = threading.Thread(target=processor.go)
            t2.start()

            t1.join()
            t2.join()

        if do_minimize:
            minimizer = TraceMinimizer(db_path, out_file)
            minimizer.go()
    finally:
        pass


main()
