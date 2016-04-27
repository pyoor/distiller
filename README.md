Distiller
========= 
A distributed corpus distillation tool for windows applications.

*Essentially a rewrite of Ben Nagy and the_grugq's [runtracer](https://github.com/grugq/RunTracer) written in python and using DynamoRIO's drcov in place of PIN.*


### Overview
----------
Distiller works in two modes:

#### Tracing:
Seeds are pushed into the beanstalk tube and distributed to clients for tracing.  The initial trace results are uniq'd and stored for later analysis.

#### Minimization:
After all seeds have been traced, a master list of unique blocks is generated.
* Seeds are sorted by largest block count.
* If a seed introduces a new block, it is added to the master list.
* If a seed contains a block with a larger instruction count than previously identified, the record is replaced.

*All records are stored in an SQLite database.  New seeds can easily be added later and reprocessed.*


### Installation:
----------
#### Server requirements:
The server components require beanstalkc, pyyaml, and msgpack:

* ```pip install beanstalkc pyyaml msgpack-python```


#### Client requirements:
The client components require beanstalkc, pyyaml, msgpack, and psutil:

* ```pip install beanstalkc pyyaml msgpack-python psutil```

The client also requires DynamoRIO.  Tested with version 6.1
    https://github.com/DynamoRIO/dynamorio/wiki/Downloads
    

### Basic Usage:
----------
Server-side:

* ```server.py -s ./seeds -d backup.db -trace -minimize -o output.csv```

Client-side:

* ```client.py --host 192.168.1.100```
