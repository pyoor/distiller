#!/usr/bin/python
from datetime import datetime
import os
import sqlite3
import csv
from common import packer


class TraceReducer:
    def __init__(self, config):
        self.sql = sqlite3.connect(config.db_path)
        self.c = self.sql.cursor()

        self.out = os.path.join(config.output_dir, "reduction-results.csv")

        self.master_bblock = {}
        self.master_bbcount = {}
        self.master_inscount = {}

        self.module_table = None

    def reduce(self):
        # ToDo: Perform an initial comparison of seed to determine percentage of master list
        # ToDo: Use this method instead of ublock_cnt to determine which seeds to parse first
        # ToDo: Rerun for each file
        self.c.execute('''SELECT seed_name FROM key_lookup ORDER BY ublock_cnt DESC''')
        seeds = self.c.fetchall()

        for seed in seeds:
            seed_name = seed[0]

            self.c.execute('''SELECT ublock_cnt, traces FROM key_lookup WHERE seed_name = ?''', [seed_name])
            data = self.c.fetchone()

            ublock_cnt = data[0]
            trace_data = packer.unpack(data[1])

            # Save seed->ublock_cnt lookup
            self.master_bbcount[seed_name] = ublock_cnt

            print "[ +D+ ] - Merging %s with %s blocks into the master list." % (seed_name, ublock_cnt)

            for bblock, ins_count in trace_data.iteritems():
                if bblock not in self.master_bblock:
                    self.master_bblock[bblock] = seed_name
                    self.master_inscount[bblock] = ins_count

                # If basic_block exists and new trace has bigger ins_count, replace it
                elif self.master_inscount[bblock] < ins_count:
                    self.master_bblock[bblock] = seed_name
                    self.master_inscount[bblock] = ins_count

    def report(self):
        # Create results table
        block_results = sorted(set(self.master_bblock.itervalues()))
        for seed_name in block_results:
            self.c.execute('INSERT INTO results VALUES (?,?)', (seed_name, self.master_bbcount[seed_name]))
        self.sql.commit()

        self.c.execute('''SELECT * FROM results''')
        seed_results = self.c.fetchall()
        print "[ +D+ ] - Reduced set to %s covering %s unique blocks." % (len(block_results), len(self.master_bblock))

        self.c.execute('''SELECT * FROM results ORDER BY ublock_cnt DESC LIMIT 1;''')
        best_seed = self.c.fetchone()
        print "[ +D+ ] - Best seed %s covers %s unique blocks." % (best_seed[0], best_seed[1])

        with open(self.out, 'wb') as f:
            writer = csv.writer(f)
            writer.writerow(['Seed Name', 'Unique Block Count'])
            writer.writerows(seed_results)
        print "[ +D+ ] - Wrote results to %s" % self.out

    def go(self):
        print "[ +D+ ] - Start reducer."
        n1 = datetime.now()

        # Reduce traces
        self.reduce()

        # Update db and output to CSV
        self.report()

        n2 = datetime.now()
        print "[ +D+ ] - Reduction completed in %ss" % (n2 - n1).seconds

