import beanstalkc
import os
import sqlite3
from time import sleep

from common import packer


class Inserter(object):
    def __init__(self, config):
        self.project_name = config.project_name
        self.db_path = config.db_path
        self.seed_dir = config.seed_dir
        self.min_dir = config.min_dir
        self.trace_queue = config.trace_queue
        self.min_queue = config.min_queue

        self.bs = beanstalkc.Connection(host='localhost')
        self.sql = sqlite3.connect(self.db_path, check_same_thread=False)
        self.c = self.sql.cursor()

    def seed_traced(self, seed_name):
        self.c.execute("SELECT num FROM seeds WHERE seed_name = ?", [seed_name])
        if self.c.fetchone() is not None:
            return True
        else:
            return False

    def seed_minimized(self, seed_name):
        min_path = os.path.join(self.min_dir, seed_name)
        if os.path.isfile(min_path):
            return True
        else:
            return False

    def insert(self, seed_path, seed_name, tube):
        with open(seed_path, 'rb') as d:
            seed_data = d.read()

        data = {
            'name': seed_name,
            'data': seed_data
        }

        seed_pack = packer.pack(data)

        self.bs.use(tube)
        while True:
            if self.bs.stats_tube(tube)['current-jobs-ready'] < 20:
                print "[ +D+ ] - Pushing seed: %s" % seed_name
                self.bs.put(seed_pack, 65536, 0, 600)
                break
            else:
                sleep(1)

        self.bs.use('default')

    def insert_seed(self):
        print "[ +D+ ] - Start Seed Inserter"
        for root, dirs, files in os.walk(self.seed_dir):
            for seed_name in files:
                seed_path = os.path.join(root, seed_name)
                if not self.seed_traced(seed_name):
                    self.insert(seed_path, seed_name, self.trace_queue)
                else:
                    print "[ +D+ ] - Trace for seed exists in database: %s" % seed_name

        print "[ +D+ ] - Seed Inserter Completed"

    def insert_mincase(self):
        print "[ +D+ ] - Start Mincase Inserter"
        self.c.execute('''SELECT seed_name FROM results''')
        for seed_name in self.c.fetchall():
            if not self.seed_minimized(seed_name):
                seed_path = os.path.join(self.seed_dir, seed_name)
                self.insert(seed_path, seed_name, self.min_queue)

        print "[ +D+ ] - Mincase Inserter Completed"
