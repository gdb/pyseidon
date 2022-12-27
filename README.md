# Pyseidon: A fork-based "load-once, run many times" Python server

![Pyseidon: A fork-based "load-once, run many times" Python server](https://i.imgur.com/DwC22BK.png)

Pyseidon implements a "load once, run many times" paradigm for any
Python workload. It's useful for speeding up load times where there's
some slow fixed setup required each time you launch a process,
followed by some dynamically changing workload.

A common use-case is preloading some slow-to-load dependencies that
don't change much; alternatively, you can use it to preload a big
dataset once.

Pyseidon works by launching a server process which performs one-time
setup; you can then dynamically connect a client to it which causes
the server to fork & run your workload in the resulting subprocess.

As a user, it feels just like running a Python script, but the
one-time setup happens exactly once.

[Poseidon](https://github.com/stripe-ctf/poseidon) is a Ruby
implementation of the same concept.

# Installation

You can install via `pip`:

```
pip install pyseidon
```

Or you can install from source:

```
git clone https://github.com/gdb/pyseidon
pip install -e pyseidon
cd pyseidon/client && make
```

# How to use

- Create & run a Pyseidon server process:

```shell
$ cat <<EOF > server.py
import pyseidon
import sys
def handler():
  print(f'Hi from worker. Your client ran with args: {sys.argv}')

pyseidon = pyseidon.Pyseidon()
pyseidon.run(handler)
EOF
$ python server.py
```

- Connect to the server process via the provided client:

```shell
$ pyseidon a b c
Hi from worker. Your client ran with args: ['a', 'b', 'c']
```

# What's going on

Pyseidon works by having the client send its stdin, stdout, and stderr
file descriptors to a worker process spawned by the server. The
workflow is the following:

- The Pyseidon server accepts a connection from a client, forking off
  a worker.
- The client sends over its argv, its current working directory, and
  its stdin, stdout, stderr file descriptors.
- The worker installs those file descriptors, cds to that working
  directory, and then executes the provided handler from the server.

The worker, having forked from the server, has full copy-on-write
access to all variables and code in the server's address space. This
means it can access any data sets that were already loaded by the
server (and can also stomp on that data or load new code without
worry).

# TODO

- Forward signals from the client
- Rewrite the client in Rust
- Find a less hacky way to compile the client
