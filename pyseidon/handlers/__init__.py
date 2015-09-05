import pyseidon
import sys

def handle_script():
    import runpy
    """
Allow the client to run an arbitrary Python script.

Here's sample usage:

```
def expensive_setup():
  ...

if __name__ == '__main__':
  expensive_setup()

  import pyseidon.handlers
  pyseidon.handlers.handle_script()
```
"""
    def handler():
        if len(sys.argv) < 1:
            print >>sys.stderr, 'Must provide path to Python script to execute'
            sys.exit(1)
        runpy.run_path(sys.argv[0], run_name='__main__')
    master = pyseidon.Pyseidon()
    master.run(handler)
