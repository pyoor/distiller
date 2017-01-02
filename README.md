Distiller
========= 
A distributed corpus distillation tool for windows applications.

*Essentially a rewrite of Ben Nagy and the_grugq's [runtracer](https://github.com/grugq/RunTracer) written in python and using DynamoRIO's drcov in place of PIN.*


### Overview
----------
Distiller can be configured to work in multiple modes.

#### Tracing
This mode distributes seeds for tracing.

#### Preprocessing
This mode prepares traces for reduction.

* A set of unique blocks covered by each trace is compressed and stored. 
* A master list containing all blocks covered by each trace is maintained.
* New blocks introduced by incoming traces are added to the master list.

#### Reduction
This mode generates the corpus from all available traces

* The trace containing the largest unique block count is selected and added to the corpus.  Blocks within this trace are removed from the master list.
* A mapping of all remaining blocks and those traces which include them is created.  This requires a single iteration of all traces within the database.
* The trace containing the next highest block count is then added to the corpus.  The blocks covered by this trace are then removed from the master list.
* This process is repeated until all blocks contained within the master list have been covered.

*All records are stored in an SQLite database.  New seeds can easily be added later and reprocessed.*


### Installation
----------
#### Server requirements
The server components require beanstalkc, pyyaml, and msgpack:

 ```pip install beanstalkc pyyaml msgpack-python```


#### Client requirements
The client components require beanstalkc, pyyaml, msgpack, and psutil:

* ```pip install beanstalkc pyyaml msgpack-python psutil```

The client also requires DynamoRIO.  Tested with version 6.1
    https://github.com/DynamoRIO/dynamorio/wiki/Downloads
    

### Basic Usage
----------
Server-side:

* ```beanstalkd -z 30000000000```
* ```python distiller.py ./configs/wordpad.yml```
```
[ +D+ ] - Start Seed Inserter
[ +D+ ] - Pushing seed: 2.rtf
[ +D+ ] - Pushing seed: 3.3.rtf
[ +D+ ] - Pushing seed: 1.2.rtf
[ +D+ ] - Pushing seed: 3.rtf
[...truncated...]
[ +D+ ] - Seed Inserter Completed
[ +D+ ] - Start preprocessor
[ +D+ ] - Processed trace for seed 2.rtf covering 5082 unique blocks
[ +D+ ] - Processed trace for seed 3.3.rtf covering 5152 unique blocks
[ +D+ ] - Processed trace for seed 1.2.rtf covering 4965 unique blocks
[ +D+ ] - Processed trace for seed 3.rtf covering 5152 unique blocks
[ +D+ ] - All traces have been processed
[ +D+ ] - Start reduction
[ +D+ ] - Reduced set to 2 covering 5157 unique blocks.
[ +D+ ] - Best seed 3.3.rtf covers 5152 unique blocks.
[ +D+ ] - Wrote results to ./results/reduction-results.csv
[ +D+ ] - Reduction completed in 0s
```

Client-side:

* ```python agent.py .\configs\wordpad.yml```
```
F:\>python agent.py configs\wordpad.yml
[ +D+ ] - Attempting to trace 2.rtf
[ +D+ ] - Attempting to trace 3.3.rtf
[ +D+ ] - Attempting to trace 1.2.rtf
[ +D+ ] - Attempting to trace 3.rtf
[...truncated...]
[ +D+ ] No trace jobs available.
```
