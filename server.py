#!/usr/bin/python

import argparse
import datetime
import csv
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time

import beanstalkc
import msgpack

max_time_to_trace = 600
pulse = threading.Event()


def start_beanstalk():
    try:
        # Check if beanstalk is already running
        global beanstalk
        beanstalk = subprocess.Popen(["beanstalkd", "-z", "50000000"])
    except OSError as e:
        if e.errno == os.errno.ENOENT:
            print "Error executing beanstalkd: file not found."
            print "Please check that beanstalkd is installed in your current path."
        else:
            print "Unknown error.  Check to ensure the port isn't already in use."
            raise
    except:
        raise


def create_db(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE key_lookup (seed_name TEXT PRIMARY KEY, block_count INT, modules BLOB, traces BLOB)''')
    conn.commit()


def insert_seed(seed_dir, db_path):
    try:
        bs_conn = beanstalkc.Connection(host='localhost', port=11300)
        bs_conn.use('seed_tube')
        for root, dirs, files in os.walk(seed_dir):
            for f in files:
                os.path.join(root, f)
                seed_name = f

                # Don't insert seeds that already exist in the database
                # Refactor: Move to database class
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                result = c.execute("SELECT * FROM key_lookup WHERE seed_name = ?", [seed_name])
                if result.fetchone() is None:
                    with open(os.path.join(root, f), 'r') as d:
                        seed_data = d.read()
                    seed = msgpack.packb([seed_name, seed_data], use_bin_type=True)
                    while True:
                        if bs_conn.stats_tube('seed_tube')['current-jobs-ready'] < 20:
                            print "[ +D+ ] - Pushing seed: %s" % seed_name
                            bs_conn.put(seed, 65536, 0, max_time_to_trace)
                            break
                        else:
                            time.sleep(1)
    except:
        raise
        print "[ +E+ ]Something went wrong during insertion."


def process(db_path, wl, bl):
    # Create new beanstalk connection for processing
    bs_conn = beanstalkc.Connection(host='localhost', port=11300)
    bs_conn.watch('results_tube')

    while True:
        # If seed jobs still exist, wait forever
        if 'seed_tube' in bs_conn.tubes():
            bs_job = bs_conn.reserve()
        else:
            # Otherwise sleep 120s for any remaining jobs
            # This could be better
            print "[ +D+ ] - No seeds remaining.  Waiting 60s for remaining traces."
            bs_job = bs_conn.reserve(timeout=60)

        if bs_job:
            trace = msgpack.unpackb(bs_job.body)
            seed_name = trace['seed_name']
            data = trace['data']

            bc = re.search('BB Table: (.*?) bbs', data)
            md = re.search(r'Module Table:.*?\n(.*?)BB Table', data, re.DOTALL)
            td = re.search(r'module id, start, size:\n(.*)', data, re.DOTALL)

            # Parse module table from file
            if bc and md and td:

                block_count = bc.group(1)
                module_data = md.group(1)
                trace_data = td.group(1)

                module_table = {}
                for m in module_data.splitlines():
                    module_num = m.rstrip().split(",")[0]
                    module_name = m.rstrip().split(",")[2]

                    # Is this a whitelisted/blacklisted module?
                    if (not wl or re.search('|'.join(wl), module_name)) and (not bl or not re.search('|'.join(bl), module_name)):
                        module_table[int(module_num)] = module_name

                # Sort and unique trace data
                trace_data = sorted(set(trace_data.splitlines()))

                module_pack = msgpack.packb(module_table)
                trace_pack = msgpack.packb(trace_data)

                # This needs to be refactored
                try:
                    conn = sqlite3.connect(db_path)
                    c = conn.cursor()
                    c.execute('INSERT INTO key_lookup VALUES (?,?,?,?)',
                              (seed_name, block_count, sqlite3.Binary(module_pack), sqlite3.Binary(trace_pack)))
                    conn.commit()
                    conn.close()
                except sqlite3.IntegrityError:
                    print "[ +E+ ] - Seed already exists in database: %s" % seed_name
                    print "[ +E+ ] - This should never happen!"

                print "[ +D+ ] - Processed trace for seed %s covering %s blocks" % (seed_name, block_count)

            # Finally, delete the job
            bs_job.delete()
        else:
            break

    print "[ +D+ ] - All traces have been preprocessed"
    # Notify minimizer to begin
    pulse.set()


def minimize(db_path, out_file):
    pulse.wait()
    print "[ +D+ ] - Begin final reduction."
    n1 = datetime.datetime.now()
    master_count = {}
    master_block = {}
    master_inscount = {}

    conn1 = sqlite3.connect(db_path)
    c1 = conn1.cursor()

    for name in c1.execute('''SELECT seed_name FROM key_lookup ORDER BY block_count DESC'''):
        seed_name = name[0]

        conn2 = sqlite3.connect(db_path)
        c2 = conn2.cursor()
        c2.execute('''SELECT block_count, modules, traces FROM key_lookup WHERE seed_name = ?''', [seed_name])
        data = c.fetchone()
        block_count = data[0]
        module_table = msgpack.unpackb(data[1])
        trace_data = msgpack.unpackb(data[2])

        # Save seed->block_count lookup
        master_count[seed_name] = block_count

        print "[ +D+ ] - Merging %s with %s blocks into the master list." % (seed_name, block_count)
        for line in trace_data:
            match = re.search("module\[(.*)\]: (.*), (.*)", line.rstrip())
            if match:
                module_id = match.group(1).strip()
                basic_block = match.group(2).strip()
                block_size = int(match.group(3).strip())

                if int(module_id) in module_table:
                    module = module_table[int(module_id)]
                    key = "%s:%s" % (module, basic_block)

                    # If basic_block doesn't exist, add it
                    if key not in master_block:
                        master_block[key] = seed_name
                        master_inscount[key] = block_size

                    # If basic_block exists and new trace has bigger ins_count, replace it
                    elif master_inscount[key] < block_size:
                        master_block[key] = seed_name
                        master_inscount[key] = block_size

    n2 = datetime.datetime.now()
    print "[ +D+ ] - Reduction completed in %s" % (n1-n2).seconds

    # Wipe results if they already exist
    c1.execute('''DROP TABLE IF EXISTS results''')
    conn1.commit()

    # Create results table
    c1.execute('''CREATE TABLE results (seed_name TEXT PRIMARY KEY, block_count INT)''')
    block_results = sorted(set(master_block.itervalues()))
    for seed_name in block_results:
        c1.execute('INSERT INTO results VALUES (?,?)', (seed_name, master_count[seed_name]))
    conn1.commit()

    c1.execute('''SELECT * FROM results''')
    seed_results = c1.fetchall()
    print "[ +D+ ] - Reduced seed set to %s covering %s unique blocks." % (len(block_results), len(master_block))

    c1.execute('''select * from results ORDER BY block_count DESC LIMIT 1;''')
    best_seed = c1.fetchone()
    print "[ +D+ ] - Best seed %s covers %s unique blocks." % (best_seed[0], best_seed[1])

    with open(out_file, 'wb') as f:
        writer = csv.writer(f)
        writer.writerow(['Seed Name', 'Block Count'])
        writer.writerows(seed_results)
    print "[ +D+ ] - Wrote results to %s" % out_file


def clean_exit():
    try:
        if 'beanstalk' in globals() and beanstalk is not None:
            beanstalk.kill()
    except:
        raise


class MyParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_help()
        sys.stderr.write('\nError: %s\n' % message)
        sys.exit(2)


def main():
    try:
        parser = MyParser(
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
    Ex. server.py --seeds ./seeds --db backup.db --trace --minimize

    Add traces to an existing set
    Ex. server.py --seeds ./seeds --db backup.db --append --trace --minimize

    Replace existing results
    Ex. server.py --seeds ./seeds --db backup.db --replace --trace --minimize
            '''
        )
        parser.add_argument("--db", help="Path to trace database", required=True, metavar='./backup.db')
        parser.add_argument("--seeds", help="Path to seeds directory", metavar='./seeds')
        parser.add_argument("--out", help="Path to save results", required=True, metavar='./output.csv')
        parser.add_argument("--append", help=argparse.SUPPRESS, action="store_true")
        parser.add_argument("--replace", help=argparse.SUPPRESS, action="store_true")
        parser.add_argument("--trace", help="Trace seeds", action="store_true")
        parser.add_argument("--minimize", help="Minimize traces", action="store_true")
        parser.add_argument("--whitelist",
                            help="Comma separated list of allowed modules.\nEx: ntdll.dll,msvcrt.dll", metavar="")
        parser.add_argument("--blacklist",
                            help="Comma separated list of blocked modules.\nEx: ntdll.dll,msvcrt.dll", metavar="")

        args = parser.parse_args()
        if not (args.trace or args.minimize):
            parser.error("No action specified.  You must specify --trace, --minimize, or both!")

        if args.db:
            db_path = args.db
            if os.path.isfile(db_path):
                db_exists = True
                if args.replace:
                    os.remove(db_path)
                    db_exists = False
                elif not args.append:
                    parser.error("Database exists.  You must specify --append or --replace!")
            else:
                db_exists = False
        if args.out:
            out_file = args.out
            if os.path.isfile(out_file):
                parser.error("Results file exists!  Please specify a new filename.")
        if args.seeds:
            seed_dir = args.seeds
            if not os.path.isdir(seed_dir):
                parser.error("Can't find seed directory.  Confirm the path is correct.")

        do_trace = True if args.trace else False
        do_minimize = True if args.minimize else False

        # Parse whitelist options
        wl = args.whitelist.split(',') if args.whitelist else False

        # Add these default blacklist modules
        bl = ['<unknown>', 'dynamorio.dll', 'drcov.dll']
        if args.blacklist:
            bl.extend(args.blacklist.split(','))

        # Create database
        if not db_exists:
            create_db(db_path)

        if do_trace:
            start_beanstalk()

            # Insert seeds into beanstalk
            inserter = threading.Thread(target=insert_seed, args=[seed_dir, db_path])
            inserter.start()

            # Start trace preprocessor
            time.sleep(10)
            processor = threading.Thread(target=process, args=[db_path, wl, bl])
            processor.start()

            inserter.join()
            processor.join()
        else:
            pulse.set()

        if do_minimize:
            # Start trace preprocessor
            minimizer = threading.Thread(target=minimize, args=[db_path, out_file])
            minimizer.start()
            minimizer.join()

    finally:
        clean_exit()


main()
