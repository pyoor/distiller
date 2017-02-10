import beanstalkc
import sqlite3
import re
import os
from common import packer


class TraceProcessor:
    def __init__(self, config):
        self.bs = beanstalkc.Connection(host='127.0.0.1', port=11300)
        self.sql = sqlite3.connect(config.db_path, check_same_thread=False)
        self.c = self.sql.cursor()

        self.trace_queue = config.trace_queue
        self.trace_results = config.trace_results

        self.flt = config.mode
        self.mods = config.modules
        self.trace_dir = config.trace_dir

        self.job = None

    def job_available(self):
        self.bs.watch(self.trace_results)
        while self.trace_queue in self.bs.tubes():
            self.job = self.bs.reserve(20)
            if self.job:
                break
        else:
            self.job = self.bs.reserve(20)

        if self.job:
            return True
        else:
            return False

    def store_results(self, seed_name, trace_name, trace_path, processed_trace):
        ublock_cnt = len(processed_trace)

        try:
            trace_pack = packer.pack(list(processed_trace))
            with open(trace_path, 'wb') as f:
                f.write(trace_pack)
        except:
            print "[ +E+ ] - Error saving trace file.  Discarding!" % trace_name
            return

        try:
            # Insert seed and update master list
            self.c.execute('BEGIN TRANSACTION')
            self.c.execute('INSERT INTO seeds VALUES (null,?,?,?)', (seed_name, trace_name, ublock_cnt))

            for bblock in processed_trace:
                self.c.execute('INSERT OR IGNORE INTO master_lookup VALUES (?)', (bblock,))

            self.sql.commit()
        except:
            print "[ +E+ ] - Error updating database.  Discarding!" % trace_name
            if os.path.isfile(trace_path):
                os.remove(trace_path)
            return

        print "[ +D+ ] - Processed trace for seed %s covering %s unique blocks" % (seed_name, ublock_cnt)

    def go(self):
        try:
            print "[ +D+ ] - Start preprocessor"
            while True:
                if self.job_available():
                    trace_job = packer.unpack(self.job.body)

                    seed_name = trace_job['seed_name']
                    trace_data = trace_job['data']

                    trace_name = os.path.splitext(seed_name)[0] + ".trace"
                    trace_path = os.path.join(self.trace_dir, trace_name)

                    md = re.search(r'Module Table:.*?\n(.*?)BB Table', trace_data, re.DOTALL)
                    td = re.search(r'module id, start, size:\n(.*)', trace_data, re.DOTALL)

                    if md and td:
                        module_data = md.group(1)
                        raw_trace = td.group(1)

                        mod_table = {}
                        for m in module_data.splitlines():
                            m_entry = m.split(",")
                            old_num = m_entry[0].strip()
                            m_name = m_entry[2].strip()

                            if (self.flt == "include" and m_name in self.mods) or (self.flt == "exclude" and m_name not in self.mods):

                                # Try to insert module_names into module lookup
                                # Will fail silently if module name already exists
                                try:
                                    self.c.execute('''INSERT INTO modules VALUES(null, ?)''', (m_name, ))
                                except sqlite3.IntegrityError:
                                    pass

                                # Retrieve new module number associated with name
                                self.c.execute('''SELECT num FROM modules WHERE name = ?''', (m_name, ))
                                new_num = self.c.fetchone()

                                mod_table[old_num] = {}
                                mod_table[old_num] = new_num[0]

                        # Update module number using the value stored in the db
                        # Only store lines containing the highest ins_cnt
                        processed_trace = set()
                        for line in raw_trace.splitlines():
                            match = re.search("module\[(.*)\]: 0x(.*), (.*)", line.strip())
                            m_num = match.group(1).strip()
                            m_ins = match.group(2)

                            # Replace module number with value stored in mod_table
                            # Append instruction address to the module number
                            # Ex. 0+0x41414141

                            # We have to check this as DynamoRio occasionally fails.
                            # Ex. module[65535]

                            if m_num in mod_table:
                                bblock = "%s+%s" % (mod_table[m_num], m_ins)
                                processed_trace.add(bblock)

                        self.store_results(seed_name, trace_name, trace_path, processed_trace)
                    else:
                        print "[ +E+ ] - Error parsing trace for seed %s.  Discarding!" % seed_name

                    self.job.delete()
                else:
                    break
            else:
                self.bs.ignore('reduction-results')

        finally:
            self.bs.close()
            self.sql.close()
            print "[ +D+ ] - All traces have been processed"
