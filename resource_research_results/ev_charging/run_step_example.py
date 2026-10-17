"""Constructed50Hz-like step, not another measured vehicle experiment."""
from pathlib import Path
import json,sys
BASE=Path(__file__).resolve().parent;sys.path.insert(0,str(BASE/'code'))
from recorded_step_response import analyze_recorded_step
t=list(range(0,15000000,20000))
# Artificial0.4s delay and1s linear change from6 to10A.
i=[6+4*min(1,max(0,(x/1e6-.4))) for x in t]
print(json.dumps({'kind':'constructed_example','features':analyze_recorded_step(t,i,6,6,10)},ensure_ascii=False,indent=2))
