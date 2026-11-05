"""Explicit assumptions for identification; training-only discrete BIC screening."""
from itertools import combinations
import math
import numpy as np
NODES=('X','W','D','A','S')
def subsets(values):
    for k in range(len(values)+1):yield from combinations(values,k)

def assumed(randomized):
    edges=[('W','A'),('D','A'),('X','S'),('W','S'),('A','S')]
    return edges if randomized else edges+[('X','D'),('W','D')]

def separated(edges,source,target,condition):
    """Moralize ancestors of source,target,Z and remove Z."""
    ancestors=set([source,target,*condition]);change=True
    while change:
        change=False
        for a,b in edges:
            if b in ancestors and a not in ancestors:ancestors.add(a);change=True
    graph={n:set() for n in ancestors}
    for a,b in edges:
        if a in ancestors and b in ancestors:graph[a].add(b);graph[b].add(a)
    for child in ancestors:
        parents=[a for a,b in edges if b==child and a in ancestors]
        for a,b in combinations(parents,2):graph[a].add(b);graph[b].add(a)
    seen=set(condition);queue=[source]
    while queue:
        a=queue.pop()
        if a in seen:continue
        if a==target:return False
        seen.add(a);queue.extend(graph[a]-seen)
    return True

def adjustment(edges):
    descendants={'D'};change=True
    while change:
        new=descendants|{b for a,b in edges if a in descendants};change=new!=descendants;descendants=new
    allowed=[v for v in ('X','W') if v not in descendants]
    backdoor=[(a,b) for a,b in edges if a!='D']
    valid=[list(s) for s in subsets(allowed) if separated(backdoor,'D','S',s)]
    return dict(valid_sets=valid,selected=valid[0] if valid else None,forbidden_post=['A','S'])

def learn(data,minimum=20):
    data=np.asarray(data,int)
    if data.ndim!=2 or data.shape[1]!=5 or not np.isin(data,[0,1]).all():raise ValueError('five binary observed nodes')
    n=len(data);allowed=[[],[],[0,1],[0,1,2],[0,1,2,3]];edges=[];scores=[]
    for node in range(5):
        candidates=[]
        for parents in subsets(allowed[node]):
            key=sum(data[:,j]*(2**k) for k,j in enumerate(parents)) if parents else np.zeros(n,int)
            count=np.bincount(key,minlength=2**len(parents));ones=np.bincount(key,weights=data[:,node],minlength=len(count));zeros=count-ones
            if min(count)<minimum:
                candidates.append(dict(parents=[NODES[j] for j in parents],available=False,minimum_parent_count=int(min(count)),bic=None));continue
            ll=0.
            for positive,total in zip(ones,count):
                negative=total-positive
                if positive:ll+=positive*math.log(positive/total)
                if negative:ll+=negative*math.log(negative/total)
            bic=-2*ll+len(count)*math.log(n)
            candidates.append(dict(parents=[NODES[j] for j in parents],available=True,minimum_parent_count=int(min(count)),bic=float(bic)))
        usable=[v for v in candidates if v['available']]
        best=min(usable,key=lambda v:(v['bic'],len(v['parents']),v['parents']))
        edges.extend((a,NODES[node]) for a in best['parents']);scores.append(dict(node=NODES[node],selected=best,candidates=candidates))
    return dict(edges=edges,local_scores=scores,direction_source='declared order; parent presence BIC data screening',suggested_adjustment=adjustment(edges))
