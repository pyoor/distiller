import yaml
import os
import sqlite3


class DistillerConfig:
    def __init__(self, config_file, section):
        self.config = read_config(config_file, section)

        try:
            self.project_name = self.config['name']
            self.trace_queue = "%s-trace-queue" % self.project_name
            self.trace_results = "%s-trace-results" % self.project_name
            self.min_queue = "%s-min-queue" % self.project_name
            self.min_results = "%s-min-results" % self.project_name
        except KeyError:
            raise Exception(" Project name not defined.")

        try:
            self.operations = self.config['operations']
            if len(self.operations) == 0:
                raise Exception("You must select atleast one mode of operation.")
        except:
            raise Exception("You must select atleast one mode of operation.")

        try:
            self.mode = self.config['filter']['mode']
            self.modules = self.config['filter']['modules']
        except KeyError:
            # Optional arguments
            self.mode = None
            self.modules = None

        if section == "server":
            try:
                self.db_path = self.config['db_path']

                action = None
                if os.path.isfile(self.db_path) and ("reduce" in self.operations or "trace" in self.operations):
                    while action != "R" and action != "A":
                        action = raw_input("Database Exists! [R]eplace or [A]ppend? ").upper()

                    if action == "R":
                        os.remove(self.db_path)

                    sql = sqlite3.connect(self.db_path)
                    c = sql.cursor()
                    c.execute('''CREATE TABLE IF NOT EXISTS modules
                    (num INTEGER PRIMARY KEY, name TEXT, UNIQUE (name))''')
                    c.execute('''CREATE TABLE IF NOT EXISTS seeds
                        (num INTEGER PRIMARY KEY, name TEXT, ublock_cnt, UNIQUE (name))''')
                    c.execute('''CREATE TABLE IF NOT EXISTS master_lookup
                    (bblock TEXT PRIMARY KEY)''')

                    # Results are calculated using the full data set
                    # Wipe if they exist
                    c.execute('''DROP TABLE IF EXISTS results''')
                    c.execute('''CREATE TABLE results (name TEXT PRIMARY KEY, ublock_cnt INT)''')
                    sql.commit()
            except KeyError:
                raise Exception("No database path defined.")

            try:
                self.seed_dir = self.config['seed_dir']
            except KeyError:
                raise Exception("No seed directory defined.")

            try:
                self.trace_dir = self.config['trace_dir']
                if not os.path.isdir(self.trace_dir):
                    try:
                        os.makedirs(self.trace_dir)
                    except os.error:
                        pass
                    except:
                        raise Exception("Could not create trace directory!")
            except KeyError:
                raise Exception("No trace directory defined.")

            try:
                if "reduce" in self.operations or "minimize" in self.operations:
                    self.output_dir = self.config['output_dir']
                    try:
                        self.min_dir = os.path.join(self.output_dir, "minimized")
                        os.makedirs(self.min_dir)
                    except os.error:
                        # Ignore if dir already exists
                        pass
                else:
                    self.output_dir = None
                    self.min_dir = None
            except KeyError:
                raise Exception("No output directory defined.")

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
