import beanstalkc
import os
import sqlite3
import msgpack
from time import sleep


class SeedInserter:
    def __init__(self, db_path, seed_dir):
        self.bs = beanstalkc.Connection(host='localhost', port=11300)
        self.sql = sqlite3.connect(db_path, check_same_thread=False)
        self.c = self.sql.cursor()
        self.seed_dir = seed_dir

    def seed_exists(self, seed_name):
        result = self.c.execute("SELECT * FROM key_lookup WHERE seed_name = ?", [seed_name])
        if result.fetchone() is None:
            return False
        else:
            return True

    def go(self):
        try:
            print "[ +D+ ] - Start seed inserter."
            self.bs.use('seeds')
            for root, dirs, files in os.walk(self.seed_dir):
                for seed_name in files:
                    os.path.join(root, seed_name)
                    if not self.seed_exists(seed_name):
                        with open(os.path.join(root, seed_name), 'r') as d:
                            seed_data = d.read()

                        data = {
                            'name': seed_name,
                            'data': seed_data
                        }

                        seed_pack = msgpack.packb(data, use_bin_type=True)

                        while True:
                            if self.bs.stats_tube('seeds')['current-jobs-ready'] < 20:
                                print "[ +D+ ] - Pushing seed: %s" % seed_name
                                self.bs.put(seed_pack, 65536, 0, 600)
                                break
                            else:
                                sleep(1)
                    else:
                        print "[ +D+ ] - Trace for seed exists in database: %s" % seed_name
        finally:
            self.bs.close()
            self.sql.close()
            print "[ +D+ ] - Finished seed inserter."
