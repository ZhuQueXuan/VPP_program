"""Isolate frozen prototype module names; no old file or receipt writes."""
import importlib,importlib.util,sys,threading
from contextlib import contextmanager
from core_io import ROOT
LOCK=threading.RLock();CACHE={}
CONFIG={
 'bridge':('work/b2_b3_integration_20261028','api',['api','guards','bridge','legacy_loader','io_utils']),
 'history':('work/b1_b2_history_20261028','api',['api','legacy','features','models','io_utils','legacy_loader']),
 'feedback':('work/b3_feedback_20261028','simulation',['simulation','model','api','safe_api'])}

@contextmanager
def isolated(kind):
    folder,entry,names=CONFIG[kind]
    with LOCK:
        saved={n:sys.modules[n] for n in names if n in sys.modules};path=sys.path[:]
        for n in names:sys.modules.pop(n,None)
        try:
            sys.path.insert(0,str(ROOT/folder))
            if kind not in CACHE:
                m=importlib.import_module(entry)
                CACHE[kind]={n:sys.modules[n] for n in names if n in sys.modules}
            else:sys.modules.update(CACHE[kind]);m=CACHE[kind][entry]
            yield m
        finally:
            for n in names:sys.modules.pop(n,None)
            sys.modules.update(saved);sys.path[:]=path

def unique(name,path):
    with LOCK:
        if name in CACHE:return CACHE[name]
        spec=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);CACHE[name]=m;return m
