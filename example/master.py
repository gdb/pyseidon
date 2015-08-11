import os
import sys
import time
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import pyseidon

pyseidon = pyseidon.Pyseidon()

# Try running things like:
#
# pyseidon-client exit 1
# pyseidon-client signal 15
def handler():
    print 'Hello from Poseidon worker! You sent the following arguments:', sys.argv
    time.sleep(100)

    if sys.argv[0] == 'exit':
        sys.exit(int(sys.argv[1]))
    elif sys.argv[0] == 'signal':
        os.kill(os.getpid(), int(sys.argv[1]))
        time.sleep(1)
        print 'Huh, signal did not kill me'

pyseidon.run(handler)
