from pathlib import Path
import importlib.util,json,hashlib,datetime
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
PREVIOUS=ROOT/'work/b1_retained_real_adapter_20261102'
DATA=ROOT/'data/ACN_real_user_benchmark_v1_20261102'
def load(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
A=load(PREVIOUS/'state_v2/adapter.py','close_retained_adapter');P=A.P;B=A.B
def native(v):return B.native(v)
def read(p):return B.read(p)
def sha(p):return B.sha(p)
def now():return B.now()
def save(name,value):
    p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as h:json.dump(native(value),h,ensure_ascii=False,indent=2,allow_nan=False)
def parent_models():return read(PREVIOUS/'model.json'),read(PREVIOUS/'state_v2/model.json')
