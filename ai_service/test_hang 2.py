import faulthandler
import signal
faulthandler.enable()
faulthandler.register(signal.SIGALRM)
import os
os.kill(os.getpid(), signal.SIGALRM) # sanity check

import threading
def dump():
    print("Dumping traceback...")
    faulthandler.dump_traceback()
    os._exit(1)
t = threading.Timer(3.0, dump)
t.start()

import langgraph.graph
print("Successfully imported!")
t.cancel()
