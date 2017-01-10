import yaml
import os
import shutil
import sqlite3
import sys


class DistillerConfig:
    def __init__(self, config_file, section):
        self.config = read_config(config_file, section)

        try:
            self.project_name = self.config['name']
        except KeyError:
            raise Exception(" Project name not defined.")

        self.trace_queue = "%s-trace-queue" % self.project_name
        self.trace_results = "%s-trace-results" % self.project_name
        self.min_queue = "%s-min-queue" % self.project_name
        self.min_results = "%s-min-results" % self.project_name

        try:
            self.operations = self.config['operations']
            if len(self.operations) == 0:
                raise Exception("You must select atleast one mode of operation.")
        except:
            raise Exception("You must select atleast one mode of operation.")

        try:
            self.mode = self.config['filter']['mode']
            self.modules = self.config['modules']
        except KeyError:
            # Optional arguments
            self.mode = None
            self.modules = None

        if section == "server":
            try:
                self.seed_dir = self.config['seed_dir']
            except KeyError:
                raise Exception("No working path defined.")

            try:
                self.working_dir = self.config['working_dir']
            except KeyError:
                raise Exception("No working path defined.")

            self.project_dir = os.path.join(self.working_dir, self.project_name)
            self.db_path = os.path.join(self.project_dir, "backup.db")
            self.min_dir = os.path.join(self.project_dir, "minimized")
            self.trace_dir = os.path.join(self.project_dir, "traces")
            self.results_dir = os.path.join(self.project_dir, "results")

            if os.path.isdir(self.project_dir):
                action = None
                while action != "R" and action != "A":
                    action = raw_input("Project Exists! Replace or Append? [R/A]: ").upper()

                if action == "R":
                    confirm = None
                    while confirm != "Y" and confirm != "N":
                        confirm = raw_input("Are you sure?  All data will be deleted! [Y/N]: ").upper()

                    if confirm == "Y":
                        shutil.rmtree(self.project_dir)
                        os.makedirs(self.project_dir)
                        os.makedirs(self.min_dir)
                        os.makedirs(self.trace_dir)
                        os.makedirs(self.results_dir)

                        sql = sqlite3.connect(self.db_path)
                        c = sql.cursor()
                        c.execute('BEGIN TRANSACTION')
                        c.execute('''CREATE TABLE IF NOT EXISTS modules
                            (num INTEGER PRIMARY KEY, name TEXT, UNIQUE (name))''')
                        c.execute('''CREATE TABLE IF NOT EXISTS seeds
                            (num INTEGER PRIMARY KEY, seed_name TEXT, trace_name TEXT, ublock_cnt INT, UNIQUE (seed_name))''')
                        c.execute('''CREATE TABLE IF NOT EXISTS master_lookup
                            (bblock TEXT PRIMARY KEY)''')

                        # Results are calculated using the full data set - Wipe if they exist!
                        c.execute('''DROP TABLE IF EXISTS results''')
                        c.execute('''CREATE TABLE results (name TEXT PRIMARY KEY, ublock_cnt INT)''')
                        sql.commit()
                    else:
                        sys.exit()

        elif section == "client":
            try:
                self.host = self.config['host']
            except KeyError:
                raise Exception("No host defined.")

            try:
                self.drio_path = self.config['drio_path']
                if not os.path.isfile(self.drio_path):
                    raise Exception("Can not find DynamoRio - %s" % self.drio_path)
            except KeyError:
                raise Exception("No DynamoRio path defined.")

            try:
                self.target_path = self.config['target_path']
                if not os.path.isfile(self.target_path):
                    raise Exception("Can not find target - %s" % self.target_path)
            except KeyError:
                raise Exception("No target path defined.")

            try:
                self.w_time = self.config['wait_time']
            except KeyError:
                raise Exception("No wait time defined.")

            try:
                self.m_time = self.config['max_timeout']
            except KeyError:
                raise Exception("No max timeout defined.")

            # Optional args
            try:
                self.target_args = self.config['target_args']
                if self.target_args is None:
                    self.target_args = ''
            except KeyError:
                self.target_args = None

            try:
                self.pre_cmd = self.config['pre_cmd']
            except KeyError:
                self.pre_cmd = None

            try:
                self.post_cmd = self.config['post_cmd']
            except KeyError:
                self.post_cmd = None


def read_config(config_file, section):
    sections = ['project', section]

    with open(config_file, 'r') as stream:
        data = yaml.load(stream)

    config = {}

    try:
        for section in sections:
            for k, v in data[section].iteritems():
                config[k] = v
    except KeyError:
        raise Exception(" Unable to find section %s" % section)

    return config
