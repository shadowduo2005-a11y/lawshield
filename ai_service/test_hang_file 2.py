import faulthandler, signal, os, threading
faulthandler.enable()
faulthandler.register(signal.SIGALRM)
import sys

_orig_read_text = None
import pathlib
_orig_read_text = pathlib.Path.read_text

def read_text_hook(self, *args, **kwargs):
    print("Reading:", self)
    return _orig_read_text(self, *args, **kwargs)

pathlib.Path.read_text = read_text_hook

def dump():
    print("Dumping traceback...")
    faulthandler.dump_traceback()
    os._exit(1)
t = threading.Timer(3.0, dump)
t.start()

import langgraph.graph
t.cancel()
