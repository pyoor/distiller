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

* ```python distiller.py ./configs/wordpad.yml```

Client-side:

* ```python agent.py .\configs\wordpad.yml```

```
[ +D+ ] - Start seed inserter
[ +D+ ] - Pushing seed: 2.rtf
[ +D+ ] - Pushing seed: 3.rtf
[ +D+ ] - Pushing seed: 1.rtf
[ +D+ ] - Finished seed inserter
[ +D+ ] - Start preprocessor
[ +D+ ] - Processed trace for seed 2.rtf covering 153849 unique blocks
[ +D+ ] - Processed trace for seed 3.rtf covering 160985 unique blocks
[ +D+ ] - Processed trace for seed 1.rtf covering 148383 unique blocks
[ +D+ ] - All traces have been processed
[ +D+ ] - Start minimizer.
[ +D+ ] - Merging 3.rtf with 160985 blocks into the master list.
[ +D+ ] - Merging 2.rtf with 153849 blocks into the master list.
[ +D+ ] - Merging 1.rtf with 148383 blocks into the master list.
[ +D+ ] - Reduced set to 3 covering 162072 unique blocks.
[ +D+ ] - Best seed 3.rtf covers 160985 unique blocks.
[ +D+ ] - Wrote results to ./results/20161127-232237.csv
[ +D+ ] - Reduction completed in 0s
```
