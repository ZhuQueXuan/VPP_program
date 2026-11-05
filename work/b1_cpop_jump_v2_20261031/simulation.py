"""Reuse prior independent mechanism with entirely new observations/seeds."""
from common import *
def generate(stage):
    old=load_module(V1/'simulation.py','_independent_paired_mechanism_v1')
    spec=read('protocol.json')['simulation'][stage];facts=[];truth=[]
    for seed in spec['seeds']:
        c,t=old.block(seed,spec['per_kind']);facts+=c;truth+=t
    write(f'facts/{stage}.json',facts);write(f'evaluator/{stage}.json',truth)
    return facts
if __name__=='__main__':
    if sys.argv[1]=='test':
        f=read('validation_freeze.json')
        for p,h in f['source_sha256'].items():assert sha(ROOT/p)==h,p
    facts=generate(sys.argv[1]);print(sys.argv[1],len(facts),'inputs;',len(facts)//2,'independent bases')
