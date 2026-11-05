"""Evaluation graph and independent d-separation oracle. Never imported by learner."""
from pathlib import Path
from itertools import combinations
import json,hashlib,csv
import numpy as np
BASE=Path(__file__).resolve().parent
NAMES=['A','B','C','D','E']
TRUE_DIRECTIONS={('A','C'),('B','C'),('C','D'),('A','E'),('D','E')}
TRUE_SKELETON={tuple(sorted(edge)) for edge in TRUE_DIRECTIONS}


def d_separated(a,b,conditioning,edges):
    """Ancestral moral graph criterion, independent of partial-correlation code."""
    ancestors={a,b}|set(conditioning)
    changed=True
    while changed:
        before=set(ancestors)
        ancestors|={u for u,v in edges if v in ancestors}
        changed=ancestors!=before
    moral={u:set() for u in ancestors}
    for u,v in edges:
        if u in ancestors and v in ancestors:
            moral[u].add(v);moral[v].add(u)
    for child in ancestors:
        parents=[u for u,v in edges if v==child and u in ancestors]
        for u,v in combinations(parents,2):
            moral[u].add(v);moral[v].add(u)
    blocked=set(conditioning)
    todo=[a];seen=set()
    while todo:
        u=todo.pop()
        if u==b:return False
        if u in seen or u in blocked:continue
        seen.add(u);todo.extend(moral[u]-blocked-seen)
    return True


def score(result):
    sk={tuple(e) for e in result['skeleton']}
    data={tuple(e) for e in result['data_directions']}
    prior={tuple(e) for e in result['tier_only_directions']}
    correct=len(sk&TRUE_SKELETON)
    ci_errors=sum(t['independent']!=d_separated(t['a'],t['b'],t['condition'],TRUE_DIRECTIONS)
        for t in result['traces'])
    return dict(skeleton_precision=correct/len(sk) if sk else 0.,
        skeleton_recall=correct/len(TRUE_SKELETON),skeleton_exact=sk==TRUE_SKELETON,
        data_direction_precision=len(data&TRUE_DIRECTIONS)/len(data) if data else None,
        data_direction_recall=len(data&TRUE_DIRECTIONS)/len(TRUE_DIRECTIONS),
        data_directions=len(data),tier_only_directions=len(prior),
        tier_only_precision=len(prior&TRUE_DIRECTIONS)/len(prior) if prior else None,
        conflicts=len(result['direction_conflicts'])+len(result['prior_conflicts']),
        ci_errors=ci_errors,ci_tests=len(result['traces']))


def equivalent_controls():
    # Cholesky factors of exactly the same covariance can be expressed by either
    # chain X->Y->Z or fork X<-Y->Z. Test observable ambiguity, not forced orientation.
    from graph_learner import learn
    chain=np.array([[1,0,0],[.8,1,0],[.56,.7,1.]])
    cov=chain@chain.T
    var_y=cov[1,1]
    fork=np.array([[np.sqrt(var_y),0,0],
        [cov[0,1]/np.sqrt(var_y),np.sqrt(cov[0,0]-cov[0,1]**2/var_y),0],
        [cov[2,1]/np.sqrt(var_y),0,np.sqrt(cov[2,2]-cov[2,1]**2/var_y)]])
    fork_cov=(fork@fork.T)[np.ix_([1,0,2],[1,0,2])]
    names=['X','Y','Z']
    chain_result=learn(cov,names)
    fork_result=learn(fork_cov,names)
    collider=np.array([[1,0,0],[.8,.7,1.],[0,1,0]])
    collider_result=learn(collider@collider.T,names)
    return dict(chain_fork_covariance_max_difference=float(np.max(abs(cov-fork_cov))),
        chain=chain_result,fork=fork_result,collider=collider_result)


def main():
    outputs=json.loads((BASE/'learned.json').read_text(encoding='utf-8'))
    receipt=json.loads((BASE/'run_receipt.json').read_text(encoding='utf-8'))
    assert hashlib.sha256((BASE/'learned.json').read_bytes()).hexdigest()==receipt['learned_sha256']
    oracle=json.loads((BASE/'oracle_learned.json').read_text(encoding='utf-8'))
    cov=np.load(BASE/'oracle_covariance.npy')
    # Independent regression residual covariance instead of inverse precision.
    ci_checks=[]
    for a,b in combinations(NAMES,2):
        others=[x for x in NAMES if x not in (a,b)]
        for k in range(4):
            for condition in combinations(others,k):
                i,j=NAMES.index(a),NAMES.index(b)
                ix=[NAMES.index(z) for z in condition]
                residual=cov[i,j] if not ix else cov[i,j]-cov[i,ix]@np.linalg.solve(cov[np.ix_(ix,ix)],cov[ix,j])
                expected=d_separated(a,b,condition,TRUE_DIRECTIONS)
                agrees=(abs(residual)<1e-10)==expected
                ci_checks.append(dict(a=a,b=b,condition=list(condition),agrees=agrees,residual_covariance=float(residual)))
    controls=equivalent_controls()
    rows=[]
    permutations_ok=True
    for n in (1000,5000):
        for seed in range(20262001,20262021):
            runs=[r for r in outputs if r['n']==n and r['seed']==seed]
            base=runs[0]['result']
            compare_keys=['skeleton','separators','colliders','data_directions','tier_only_directions','direction_conflicts','prior_conflicts']
            same=all(all(run['result'][key]==base[key] for key in compare_keys) for run in runs)
            permutations_ok&=same
            rows.append(dict(n=n,seed=seed,permutation_agreement=same,**score(base)))
    with (BASE/'metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary=[]
    for n in (1000,5000):
        r=[row for row in rows if row['n']==n]
        fields=['skeleton_precision','skeleton_recall','skeleton_exact','data_direction_precision','data_direction_recall','data_directions','tier_only_directions','tier_only_precision','conflicts','ci_errors','ci_tests']
        summary.append(dict(n=n,replicates=len(r),**{key:float(np.mean([row[key] for row in r if row[key] is not None])) for key in fields}))
    oracle_scores=[score(o['result']) for o in oracle]
    oracle_same=all(o['result']['skeleton']==oracle[0]['result']['skeleton'] and o['result']['separators']==oracle[0]['result']['separators'] and o['result']['data_directions']==oracle[0]['result']['data_directions'] for o in oracle)
    checks=dict(all_population_ci_agree=all(c['agrees'] for c in ci_checks),population_ci_cases=len(ci_checks),
        oracle_all_skeleton_exact=all(s['skeleton_exact'] for s in oracle_scores),oracle_120_permutations_same=oracle_same,
        finite_200_runs_5permutations_same=permutations_ok,
        chain_fork_covariance_equal=controls['chain_fork_covariance_max_difference']<1e-12,
        chain_fork_no_data_orientation=not controls['chain']['data_directions'] and not controls['fork']['data_directions'],
        collider_orients_two=controls['collider']['data_directions']==[['X','Y'],['Z','Y']])
    out=dict(identity='synthetic_linear_gaussian_method_check_only',summary=summary,
        oracle_score=oracle_scores[0],checks=checks,ci_checks=ci_checks,controls=controls,
        finite_failures=[r for r in rows if not r['skeleton_exact'] or r['conflicts']],
        limitation='limited collider/tier orientation, no Meek closure; not complete CPDAG or real EV graph')
    (BASE/'evaluation.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(dict(summary=summary,checks=checks,finite_failure_count=len(out['finite_failures'])),indent=2))
    assert all(v for k,v in checks.items() if isinstance(v,bool))

if __name__=='__main__':main()
