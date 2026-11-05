"""Five-node transparent stable skeleton and limited orientation, not full PC CPDAG."""
from itertools import combinations
import math
import numpy as np
from scipy.stats import norm


def partial_correlation(cov, i, j, condition):
    ix=[i,j]+list(condition)
    sub=cov[np.ix_(ix,ix)]
    precision=np.linalg.inv(sub)
    scale=precision[0,0]*precision[1,1]
    if scale<=0 or not np.isfinite(precision).all():
        raise ValueError('singular or invalid covariance')
    return float(np.clip(-precision[0,1]/math.sqrt(scale),-1+1e-15,1-1e-15))


def learn(cov,names,n=None,alpha=.01,tiers=None,oracle_tolerance=1e-10):
    names=list(names)
    if len(set(names))!=len(names) or cov.shape!=(len(names),len(names)):
        raise ValueError('unique names and matching covariance required')
    lookup={name:i for i,name in enumerate(names)}
    canonical=sorted(names)
    adjacent={name:set(names)-{name} for name in names}
    separators={}
    traces=[]
    for depth in range(len(names)-1):
        snapshot={key:set(values) for key,values in adjacent.items()}
        deletions=[]
        any_candidates=False
        for a,b in combinations(canonical,2):
            if b not in snapshot[a]:continue
            candidates=set()
            for side,other in ((a,b),(b,a)):
                candidates.update(tuple(s) for s in combinations(sorted(snapshot[side]-{other}),depth))
            if candidates:any_candidates=True
            found=[]
            for condition in sorted(candidates):
                rho=partial_correlation(cov,lookup[a],lookup[b],[lookup[s] for s in condition])
                if n is None:
                    p=None
                    independent=abs(rho)<oracle_tolerance
                else:
                    if n<=len(condition)+3:
                        raise ValueError('insufficient rows for Fisher-z')
                    z=math.sqrt(n-len(condition)-3)*math.atanh(rho)
                    p=float(2*norm.sf(abs(z)))
                    independent=p>alpha
                traces.append(dict(a=a,b=b,condition=list(condition),rho=rho,p=p,independent=bool(independent),depth=depth))
                if independent:found.append(list(condition))
            if found:
                deletions.append((a,b))
                separators[a+'|'+b]=found
        for a,b in deletions:
            adjacent[a].discard(b);adjacent[b].discard(a)
        if not any_candidates:break
    edges=[list(pair) for pair in combinations(canonical,2) if pair[1] in adjacent[pair[0]]]
    requests=set()
    colliders=[]
    ambiguous_triples=[]
    for middle in canonical:
        for a,c in combinations(sorted(adjacent[middle]),2):
            if c in adjacent[a]:continue
            seps=separators.get('|'.join(sorted((a,c))))
            if seps is None:
                ambiguous_triples.append([a,middle,c]);continue
            absent=[middle not in condition for condition in seps]
            if all(absent):
                colliders.append([a,middle,c])
                requests.add((a,middle));requests.add((c,middle))
            elif any(absent):ambiguous_triples.append([a,middle,c])
    conflicts=sorted([list(e) for e in requests if (e[1],e[0]) in requests])
    data_directions=sorted([list(e) for e in requests if (e[1],e[0]) not in requests])
    tier_only=[]
    prior_conflicts=[]
    if tiers is not None:
        for a,b in edges:
            if tiers[a]==tiers[b]:continue
            forward=(a,b) if tiers[a]<tiers[b] else (b,a)
            if list(forward[::-1]) in data_directions:
                prior_conflicts.append(list(forward))
            elif list(forward) not in data_directions:
                tier_only.append(list(forward))
    return dict(skeleton=edges,separators=separators,colliders=colliders,
        ambiguous_triples=ambiguous_triples,data_directions=data_directions,
        tier_only_directions=sorted(tier_only),direction_conflicts=conflicts,
        prior_conflicts=prior_conflicts,traces=traces,
        orientation_scope='colliders and separately marked time tiers; no Meek closure')
