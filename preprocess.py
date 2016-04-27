import beanstalkc
import sqlite3
import msgpack
import zlib
import re


class TraceProcessor:
    def __init__(self, db_path, wl, bl):
        self.bs = beanstalkc.Connection(host='127.0.0.1', port=11300)
        self.sql = sqlite3.connect(db_path, check_same_thread=False)
        self.c = self.sql.cursor()

        self.wl = wl
        self.bl = bl

        self.job = None

    def get_job(self):
        self.bs.watch('results')
        while 'seeds' in self.bs.tubes():
            self.job = self.bs.reserve(60)
            if self.job:
                break
        else:
            self.job = self.bs.reserve(60)

        if self.job:
            return True
        else:
            return False

    def go(self):
        print "[ +D+ ] - Start preprocessor."
        while True:
            # Hackish
            # May fail with multiple threads
            if self.get_job():
                trace = msgpack.unpackb(zlib.decompress(self.job.body))
                seed_name = trace['seed_name']
                data = trace['data']

                bc = re.search('BB Table: (.*?) bbs', data)
                md = re.search(r'Module Table:.*?\n(.*?)BB Table', data, re.DOTALL)
                td = re.search(r'module id, start, size:\n(.*)', data, re.DOTALL)

                if bc and md and td:
                    block_count = bc.group(1)
                    module_data = md.group(1)
                    raw_trace = td.group(1)

                    module_table = {}
                    for m in module_data.splitlines():
                        m_entry = m.split(",")
                        old_num = m_entry[0].strip()
                        module_name = m_entry[2].strip()

                        # Try to insert module_names into module lookup
                        # Will fail silently if module name already exists
                        try:
                            self.c.execute('''INSERT INTO modules VALUES(null, ?)''', (module_name, ))
                        except sqlite3.IntegrityError:
                            pass

                        # Retrieve new module number associated with name
                        self.c.execute('''SELECT num FROM modules WHERE name = ?''', (module_name, ))
                        new_num = self.c.fetchone()

                        module_table[old_num] = new_num[0]

                    # Update module number using the value stored in the db
                    # Only store lines containing the highest ins_cnt
                    trace_data = {}
                    for line in raw_trace.splitlines():
                        match = re.search("module\[(.*)\]: (.*), (.*)", line.strip())
                        m_num = match.group(1).strip()
                        m_ins = match.group(2)
                        ins_cnt = int(match.group(3))

                        # Replace module number with value stored in module_table
                        # Append instruction address to the module number
                        # Ex. 0+0x41414141

                        # We have to check this as DynamoRio occasionally fails.
                        # Ex. module[65535]
                        if m_num in module_table:
                            bblock = "%s+%s" % (module_table[m_num], m_ins)

                            # If the bblock doesn't exist, add it
                            # If it does and has a higher ins_cnt, replace it
                            if bblock in trace_data:
                                if trace_data[bblock] < ins_cnt:
                                    trace_data[bblock] = ins_cnt
                            else:
                                trace_data[bblock] = ins_cnt

                    trace_pack = zlib.compress(msgpack.packb(trace_data))

                    # This should be refactored
                    try:
                        self.c.execute('INSERT INTO key_lookup VALUES (?,?,?)',
                                       (seed_name, block_count, sqlite3.Binary(trace_pack), ))
                        self.sql.commit()
                    except sqlite3.IntegrityError:
                        print "[ +E+ ] - Seed already exists in database: %s" % seed_name
                        print "[ +E+ ] - This should never happen!"

                    print "[ +D+ ] - Processed trace for seed %s covering %s blocks" % (seed_name, block_count)
                self.job.delete()
            else:
                break
        else:
            self.bs.ignore('results')

        print "[ +D+ ] - All traces have been processed"
