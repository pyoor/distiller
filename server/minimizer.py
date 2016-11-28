import beanstalkc
import sqlite3
import os
import msgpack
from time import sleep
import zlib


class SeedMinimizer:
    def __init__(self, config):
        self.sql = sqlite3.connect(config['db_path'], check_same_thread=False)
        self.c = self.sql.cursor()

        self.min_dir = os.path.join(config['output_path'], "minimized")
        self.seed_dir = config['seed_path']

        self.job = None

    def is_minimized(self, seed_name):
        min_name = os.path.join(self.min_dir, seed_name)
        if os.path.isfile(min_name):
            return True
        else:
            return False

    def get_job(self):
        self.bs.watch('min-results')
        while 'min-queue' in self.bs.tubes():
            self.job = self.bs.reserve(20)
            if self.job:
                break
        else:
            self.job = self.bs.reserve(20)

        if self.job:
            return True
        else:
            return False

    def insert_seeds(self):
        print "[ +D+ ] - Begin seed insertion for minimization"
        bs = beanstalkc.Connection(host='127.0.0.1', port=11300)
        bs.use('min-queue')

        try:
            self.c.execute('''SELECT seed_name FROM results''')
            seeds = self.c.fetchall()
            for seed_name in seeds:
                if not self.is_minimized(seed_name):
                    with open(os.path.join(self.seed_dir, seed_name), 'rb') as d:
                        seed_data = d.read()

                    data = {
                        'name': seed_name,
                        'data': seed_data
                    }

                    seed_pack = msgpack.packb(data, use_bin_type=True)

                    while True:
                        if bs.stats_tube('minimize')['current-jobs-ready'] < 20:
                            print "[ +D+ ] - Pushing seed: %s" % seed_name

                            # Allow 4 hours for minimization - hackish
                            # Fix this later by touching the job after each successful action
                            bs.put(seed_pack, ttr=14400)
                            break
                        else:
                            sleep(1)
        finally:
            bs.close()
            self.sql.close()
            print "[ +D+ ] - All seeds inserted for minimization"

    def process_results(self):
        print "[ +D+ ] - Begin processing minimization results"
        bs = beanstalkc.Connection(host='127.0.0.1', port=11300)
        bs.use('min-results')

        if self.get_job():
            seed = msgpack.unpackb(zlib.decompress(self.job.body))
            name = seed['seed_name']
            data = seed['data']

            filename = os.path.join(self.min_dir, name)
            with open(filename, 'wb') as f:
                f.write(data)

