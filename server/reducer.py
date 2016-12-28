#!/usr/bin/python
import csv
import os
import sqlite3
from datetime import datetime

from common import packer


class TraceReducer:
    def __init__(self, config):
        self.sql = sqlite3.connect(config.db_path)
        self.c = self.sql.cursor()
        self.out = os.path.join(config.output_dir, "reduction-results.csv")
        self.master_bblock = self.retrieve_master()
        self.master_bbcount = len(self.master_bblock)
        self.results = []

    def retrieve_master(self):
        try:
            self.c.execute('''SELECT * FROM master_lookup''')
            res = self.c.fetchall()
            master_bblock = [i[0] for i in res]
        except:
            raise Exception("Error retrieving master list!")

        return master_bblock

    def remove_from_master(self, bblocks):
        # Remove blocks array from master_list
        temp = set(self.master_bblock) - set(bblocks)
        self.master_bblock = temp

    def reduce(self):
        # Retrieve best seed
        try:
            self.c.execute('''SELECT num, trace FROM seeds ORDER BY ublock_cnt DESC LIMIT 1''')
            row = self.c.fetchone()
            best_seed = row[0]
            best_trace = packer.unpack(row[1])
        except:
            raise Exception("Can't reduce - No seeds found!")

        self.results.append(best_seed)
        self.remove_from_master(best_trace)

        blockmap = {}
        self.c.execute('''SELECT num, trace FROM seeds''')
        for row in self.c:
            seed = row[0]
            trace = packer.unpack(row[1])
            blockmap[seed] = list(set(self.master_bblock).intersection(trace))

        r_seed = best_seed
        while self.master_bblock:
            # Remove seeds already in results from blockmap
            del blockmap[r_seed]

            # Find next seed with the most matches
            hitcount = {}
            for seed, bblock in blockmap.iteritems():
                # Recalculate similar items between both lists
                hitcount[seed] = list(set(self.master_bblock).intersection(blockmap[seed]))

            r_seed = max(hitcount, key=lambda x: len(set(hitcount[x])))
            self.results.append(r_seed)
            self.remove_from_master(blockmap[r_seed])

    def report(self):
        # Create results table
        self.c.execute('BEGIN TRANSACTION')
        for seed in self.results:
            self.c.execute('INSERT INTO results SELECT name, ublock_cnt FROM seeds WHERE NUM = ?', (seed,))
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

        # Update db and output to CSV
        self.report()

        n2 = datetime.now()
        print "[ +D+ ] - Reduction completed in %ss" % (n2 - n1).seconds

