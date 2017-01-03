import sys
sys.path.append("../")

import os
import re
import tempfile
from time import sleep
from client import runner
from utils.config_import import DistillerConfig


class TargetEvaluator:
    def __init__(self, config):
        self.d_path = config.drio_path
        self.t_path = config.target_path
        self.t_args = config.target_args
        self.w_time = config.w_time
        self.m_time = config.m_time
        self.project_name = config.project_name

        self.flt = config.mode
        self.mods = config.modules

        self.s_name = None
        self.s_data = None  # Original seed data
        self.i_data = None  # Interim seed data
        self.t_data = None  # Testing seed data
        self.temp = None

        self.mod_table = []
        self.baseline = None
        self.diff = set()
        self.collection = []

    def prepare_data(self, seed):
        self.s_name = os.path.basename(seed)
        with open(seed, 'rb') as f:
            self.s_data = f.read()

        ext = os.path.splitext(self.s_name)[1]

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as self.temp:
            self.temp.write(self.s_data)

    def clean(self):
        while True:
            try:
                if os.path.isfile(self.temp.name):
                    os.remove(self.temp.name)
            except WindowsError:
                print "[ +E+ ] - Error deleting file."
                sleep(1)
            else:
                break

    def parse(self, data):
        trace_data = set()

        md = re.search(r'Module Table:.*?\n(.*?)BB Table', data, re.DOTALL)
        td = re.search(r'module id, start, size:\n(.*)', data, re.DOTALL)

        if md and td:
            module_data = md.group(1)
            raw_trace = td.group(1)

            temp_mod_table = {}
            for m in module_data.splitlines():
                m_entry = m.split(",")
                old_num = m_entry[0].strip()
                m_name = m_entry[2].strip()

                if (self.flt == "include" and m_name in self.mods) or (
                        self.flt == "exclude" and m_name not in self.mods):

                    if m_name in self.mod_table:
                        temp_mod_table[old_num] = self.mod_table.index(m_name)
                    else:
                        self.mod_table.append(m_name)
                        temp_mod_table[old_num] = self.mod_table.index(m_name)

            # Update module number using the value stored in the db
            # Only store lines containing the highest ins_cnt
            for line in raw_trace.splitlines():
                match = re.search("module\[(.*)\]: (.*), (.*)", line.strip())
                m_num = match.group(1).strip()
                m_ins = match.group(2)

                # Replace module number with value stored in temp_mod_table
                # Append instruction address to the module number
                # Ex. 0+0x41414141

                # We have to check this as DynamoRio occasionally fails.
                # Ex. module[65535]

                if m_num in temp_mod_table:
                    bblock = "%s+%s" % (temp_mod_table[m_num], m_ins)
                    trace_data.add(bblock)

        return trace_data

    def go(self):
        print "[ +D+ ] - Establishing baseline for seed: %s" % os.path.basename(self.s_name)

        while len(self.collection) < 20:
            logfile = runner.run(self.d_path, self.t_path, self.t_args, self.temp.name, self.w_time, self.m_time)

            if logfile is not None:
                trace_data = self.parse(logfile)
                if trace_data:
                    self.collection.append(trace_data)
                    print "[ +D+ ] - Trace %d covered %d blocks" % (len(self.collection), len(trace_data))
            else:
                print "[ +E+ ] - Error retrieving log file. Restarting."

        # Select the smallest trace to use as a baseline
        # ToDo: Calculate variance and add check to ensure trace isn't too small.  Something may have gone wrong
        self.baseline = min(self.collection, key=len)
        best = max(self.collection, key=len)

        # Identify blocks common to all traces
        for trace in self.collection:
            self.baseline = self.baseline.intersection(trace)

        for trace in self.collection:
            self.diff.update(trace.difference(self.baseline))

        mods = set()
        for bblock in self.diff:
            m, b = bblock.split('+')
            mods.add(self.mod_table[int(m)])

        print "\nIdentified %d blocks common in all test cases.\n" % (len(self.baseline))

        print "Identified %d blocks that were not executed in all test cases." % (len(self.diff))
        print "-----------------------------------------------------------------"
        print ', '.join(str(x) for x in self.diff) + "\n"

        print "The following modules where found to execute blocks that do not occur in all test cases."
        print "It is recommended that you blacklist these modules."
        print "-----------------------------------------------------------------"
        print ', '.join(str(x) for x in mods)

        self.clean()


def main(config_file, seed):
    cfg = DistillerConfig(config_file, 'client')

    evaluator = TargetEvaluator(cfg)
    evaluator.prepare_data(seed)
    evaluator.go()


def usage():
    print "Usage:", sys.argv[0], "<config.yml> <seed_file>"

if __name__ == "__main__":
    if len(sys.argv) != 3:
        usage()
    else:
        main(sys.argv[1], sys.argv[2])
