# Pyseidon

A Python analogue of [Poseidon](https://github.com/stripe-ctf/poseidon).

Pyseidon supports a "static load once, dynamic run many times"
paradigm for your workload. It can be used for tasks such as loading a
dataset once and then performing many experiments on it over time.

# How to use

- Create a master Pyseidon process:

```python
import pyseidon
def handler(argv):
  print 'Hi from worker process. Your client ran with args:', argv

pyseidon = pyseidon.Pyseidon()
pyseidon.run(handler)
```

- Connect to the process via the provided client:

```shell
$ cd pyseidon/client && make
[...]
$ ./pyseidon-client sample args
Hi from worker process. Your client ran with args: ['sample', 'args']
```

# What's going on

Pyseidon works by having the client send its stdin, stdout, and stderr
file descriptors to a worker process spawned by the master. The
workflow is the following:

- The Pyseidon master accepts a connection from a client, forking off
  a worker.
- The client sends over its argv, its current working directory, and
  its stdin, stdout, stderr file descriptors.
- The worker installs those file descriptors, cds to that working
  directory, and then executes the provided handler from the master.

The worker, having forked from the master, has full copy-on-write
access to all variables and code in the master's address space. This
means it can access any data sets that were already loaded by the
master (and can also stomp on that data or load new code without
worry).
