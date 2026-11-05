"""Disjoint development cases only; no main seed scores or tuning."""
import numpy as np
from core_io import BASE,write
from generate import build
from controller import simulate
from experiment import metrics
def main():
    cases,a=build(3,2810200000);rows=[]
    for i,v in enumerate(cases):
        r=simulate(v['public'],v['arrival_stream'],a['factors'][i],a['ua'][i],a['us'][i],a['pa'][i],a['ps'][i]);m=metrics(v['public'],r)
        assert m['hard_shared_violation_kw']<1e-7
        if v['regime']!='stress':assert m['terminal_ok'] and m['ev_deadline_ok'] and all(x['strict_success'] for x in m['calls'] if x['admitted'])
        rows.append(dict(id=v['id'],**m))
    write(BASE/'development_check.json',dict(status='passed',seed=2810200003,cases=len(rows),main_seed_not_used=True,rows=rows));print('development complete',len(rows),flush=True)
if __name__=='__main__':main()
