#!/usr/bin/python
import csv
import os
import sqlite3
from common import packer
from datetime import datetime


class TraceReducer:
    def __init__(self, config):
        self.sql = sqlite3.connect(config.db_path)
        self.c = self.sql.cursor()

        self.trace_dir = config.trace_dir

        self.master_bblock = self.retrieve_master()
        self.master_bbcount = len(self.master_bblock)

        self.results = []
        self.out = os.path.join(config.project_dir, "reduction-results.csv")

    def retrieve_master(self):
        try:
            self.c.execute('''SELECT * FROM master_lookup''')
            res = self.c.fetchall()
            master_bblock = set([i[0] for i in res])
        except:
            raise Exception("Error retrieving master list!")

        return master_bblock

    def remove_from_master(self, bblocks):
        # Remove blocks array from master_list
        temp = self.master_bblock - set(bblocks)
        self.master_bblock = temp

    def import_trace(self, trace_name):
        trace_path = os.path.join(self.trace_dir, trace_name)
        with open(trace_path, 'rb') as f:
            raw = f.read()

        trace = packer.unpack(raw)

        return trace

    def reduce(self):
        # Retrieve best seed
        self.c.execute('''SELECT num, seed_name, trace_name FROM seeds ORDER BY ublock_cnt DESC LIMIT 1''')
        row = self.c.fetchone()

        if row:
            b_num, b_name, bt_name = row
        else:
            return
            print "[ +E+ ] - Can't perform reduction.  No seeds found!"

        trace = self.import_trace(bt_name)
        self.results.append(b_num)
        self.remove_from_master(trace)

        blockmap = {}
        self.c.execute('''SELECT num, seed_name, trace_name FROM seeds WHERE num != ?''', (b_num, ))
        for row in self.c:
            s_num, s_name, t_name = row

            trace = self.import_trace(t_name)
            blockmap[s_num] = list(self.master_bblock.intersection(trace))

        # Iterate over traces until all blocks have been consumed
        while self.master_bblock:
            # Find next seed with the most matches
            hitcount = {}
            for seed, bblock in blockmap.iteritems():
                # Recalculate similar items between both lists
                hitcount[seed] = list(self.master_bblock.intersection(blockmap[seed]))

            r_seed = max(hitcount, key=lambda x: len(hitcount[x]))
            self.results.append(r_seed)
            self.remove_from_master(blockmap[r_seed])
            del blockmap[r_seed]

        # Update db and output to CSV
        self.report()

    def report(self):
        # Create results table
        self.c.execute('BEGIN TRANSACTION')
        for seed in self.results:
            self.c.execute('INSERT INTO results SELECT seed_name, ublock_cnt FROM seeds WHERE NUM = ?', (seed,))
        self.sql.commit()

        print "[ +D+ ] - Reduced set to %d covering %s unique blocks." % (len(self.results), self.master_bbcount)

        self.c.execute('''SELECT * FROM results ORDER BY ublock_cnt DESC''')
        results = self.c.fetchall()
        print "[ +D+ ] - Best seed %s covers %s unique blocks." % (results[0][0], results[0][1])

        with open(self.out, 'wb') as f:
            writer = csv.writer(f)
            writer.writerow(['Seed Name', 'Unique Block Count'])
            for row in results:
                writer.writerow(row)
        print "[ +D+ ] - Wrote results to %s" % self.out

    def go(self):
        print "[ +D+ ] - Start reduction"
        n1 = datetime.now()

        # Reduce traces
        self.reduce()

        n2 = datetime.now()
        print "[ +D+ ] - Reduction completed in %ss" % (n2 - n1).seconds

