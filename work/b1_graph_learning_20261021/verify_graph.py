"""Independent graph readback: raw residual regression and path-based d-separation.

Does not import graph_learner, generate, run_study, or evaluate_graph.
"""
from pathlib import Path
from itertools import combinations
import json,math,hashlib,csv,ast
import numpy as np
from scipy.stats import norm
BASE=Path(__file__).resolve().parent
PROJECT=BASE.parent.parent
EDGES={('A','C'),('B','C'),('C','D'),('A','E'),('D','E')}
CHECKS=[]


def require(name,ok,detail=None):
    CHECKS.append(dict(name=name,passed=bool(ok),detail=detail))


def residual_ci(x,i,j,condition):
    y=x[:,[i,j]]
    z=np.column_stack([np.ones(len(x))]+[x[:,k] for k in condition])
    residual=y-z@np.linalg.lstsq(z,y,rcond=None)[0]
    dot=residual.T@residual
    rho=float(dot[0,1]/math.sqrt(dot[0,0]*dot[1,1]))
    zvalue=math.sqrt(len(x)-len(condition)-3)*math.atanh(rho)
    return rho,float(2*norm.sf(abs(zvalue)))


def path_independent(a,b,condition):
    vertices=set(sum(([u,v] for u,v in EDGES),[]))
    adjacency={v:set() for v in vertices}
    for u,v in EDGES:adjacency[u].add(v);adjacency[v].add(u)
    descendants={v:set() for v in vertices}
    for v in vertices:
        pending=[w for u,w in EDGES if u==v]
        while pending:
            w=pending.pop()
            if w in descendants[v]:continue
            descendants[v].add(w);pending.extend(t for s,t in EDGES if s==w)
    stack=[[a]]
    while stack:
        path=stack.pop()
        if path[-1]==b:
            open_path=True
            for before,middle,after in zip(path,path[1:],path[2:]):
                collider=(before,middle) in EDGES and (after,middle) in EDGES
                if collider:
                    open_path&=middle in condition or bool(descendants[middle]&set(condition))
                else:open_path&=middle not in condition
            if open_path:return False
        else:
            stack.extend(path+[v] for v in adjacency[path[-1]] if v not in path)
    return True


def independent_skeleton(x,names,alpha):
    adj={u:set(names)-{u} for u in names}
    separators={}
    for k in range(len(names)-1):
        old={u:sorted(v) for u,v in adj.items()}
        remove=[]
        for a,b in combinations(sorted(names),2):
            if b not in adj[a]:continue
            options={tuple(s) for origin,other in ((a,b),(b,a))
                for s in combinations([v for v in old[origin] if v!=other],k)}
            accepted=[]
            for condition in sorted(options):
                _,p=residual_ci(x,names.index(a),names.index(b),[names.index(u) for u in condition])
                if p>alpha:accepted.append(list(condition))
            if accepted:remove.append((a,b));separators[a+'|'+b]=accepted
        for a,b in remove:adj[a].remove(b);adj[b].remove(a)
    return [list(pair) for pair in combinations(sorted(names),2) if pair[1] in adj[pair[0]]],separators


def main():
    protocol=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))
    raw=PROJECT/protocol['raw_root']/'observations.npz'
    xdata=np.load(raw)
    outputs=json.loads((BASE/'learned.json').read_text(encoding='utf-8'))
    evaluation=json.loads((BASE/'evaluation.json').read_text(encoding='utf-8'))
    cov=np.load(BASE/'oracle_covariance.npy')
    names=protocol['nodes']
    require('40 raw numeric datasets',len(xdata.files)==40)
    require('200 learned order variants',len(outputs)==200)
    for ci in evaluation['ci_checks']:
        expected=path_independent(ci['a'],ci['b'],set(ci['condition']))
        require('path oracle '+ci['a']+ci['b']+str(ci['condition']),expected==(abs(ci['residual_covariance'])<1e-10))
    maxrho=0.;maxp=0.
    true_sk={frozenset(edge) for edge in EDGES}
    rows=[]
    for n in protocol['sample_sizes']:
        for seed in protocol['replicate_seeds']:
            x=xdata[f'n{n}_seed{seed}']
            require(f'{n}/{seed}: raw shape',x.shape==(n,5) and np.isfinite(x).all())
            runs=[r for r in outputs if r['n']==n and r['seed']==seed]
            base=runs[0]['result']
            sk,seps=independent_skeleton(x,names,protocol['alpha'])
            require(f'{n}/{seed}: raw least-squares independent skeleton',sk==base['skeleton'])
            require(f'{n}/{seed}: all minimum-depth separators',seps==base['separators'])
            keys=['skeleton','separators','colliders','data_directions','tier_only_directions','prior_conflicts','direction_conflicts']
            require(f'{n}/{seed}: all five orders same',all(all(r['result'][k]==base[k] for k in keys) for r in runs))
            for trace in base['traces']:
                rho,p=residual_ci(x,names.index(trace['a']),names.index(trace['b']),[names.index(z) for z in trace['condition']])
                maxrho=max(maxrho,abs(rho-trace['rho']));maxp=max(maxp,abs(p-trace['p']))
                require(f'{n}/{seed}: CI decision '+str((trace['a'],trace['b'],trace['condition'])),(p>.01)==trace['independent'])
            found={frozenset(e) for e in sk}
            tp=len(found&true_sk)
            directed={tuple(e) for e in base['data_directions']}
            tier={tuple(e) for e in base['tier_only_directions']}
            ci_errors=sum(t['independent']!=path_independent(t['a'],t['b'],set(t['condition'])) for t in base['traces'])
            rows.append(dict(n=n,seed=seed,skeleton_precision=tp/len(found),skeleton_recall=tp/len(true_sk),
                skeleton_exact=found==true_sk,data_direction_precision=len(directed&EDGES)/len(directed) if directed else None,
                data_direction_recall=len(directed&EDGES)/5,data_directions=len(directed),tier_only_directions=len(tier),
                tier_only_precision=len(tier&EDGES)/len(tier) if tier else None,
                conflicts=len(base['direction_conflicts'])+len(base['prior_conflicts']),ci_errors=ci_errors,ci_tests=len(base['traces'])))
    persisted=list(csv.DictReader((BASE/'metrics.csv').open(encoding='utf-8-sig',newline='')))
    for row,check in zip(persisted,rows):
        for key,value in check.items():
            actual=row[key]
            if value is None:ok=actual==''
            elif isinstance(value,bool):ok=actual==str(value)
            else:ok=abs(float(actual)-value)<1e-12
            require('metric '+str((check['n'],check['seed'],key)),ok)
    require('raw residual rho agreement',maxrho<1e-12,maxrho)
    require('raw residual Fisher-z p agreement',maxp<1e-12,maxp)
    freeze=json.loads((BASE/'source_freeze.json').read_text(encoding='utf-8'))
    for name,sha in freeze.items():
        target='evaluate_graph_serialization_failed.py' if name=='evaluate_graph.py' else name
        require('frozen source '+name,hashlib.sha256((BASE/target).read_bytes()).hexdigest()==sha)
    old=(BASE/'evaluate_graph_serialization_failed.py').read_text(encoding='utf-8')
    new=(BASE/'evaluate_graph.py').read_text(encoding='utf-8')
    require('evaluation repair only scalar bool serialization',new==old.replace('agrees=(abs(residual)<1e-10)==expected','agrees=bool((abs(residual)<1e-10)==expected)'))
    source=(BASE/'graph_learner.py').read_text(encoding='utf-8')
    tree=ast.parse(source)
    require('learner no evaluator/generator import',not any(isinstance(a,ast.ImportFrom) and a.module in ('evaluate_graph','generate') for a in ast.walk(tree)))
    require('learner does not open truth/raw files',not any(isinstance(a,ast.Call) and isinstance(a.func,ast.Name) and a.func.id=='open' for a in ast.walk(tree)))
    controls=evaluation['controls']
    require('chain/fork observational ambiguity retained',controls['chain_fork_covariance_max_difference']<1e-12 and controls['chain']['data_directions']==controls['fork']['data_directions']==[])
    require('collider control',controls['collider']['data_directions']==[['X','Y'],['Z','Y']])
    out=dict(identity='independent_readback_only',checks=CHECKS,check_count=len(CHECKS),
        failed=sum(not c['passed'] for c in CHECKS),max_raw_residual_rho_difference=maxrho,
        max_raw_residual_p_difference=maxp,
        hashes={name:hashlib.sha256((BASE/name).read_bytes()).hexdigest() for name in ('graph_learner.py','generate.py','run_study.py','evaluate_graph.py','verify_graph.py','learned.json','protocol.json')},
        raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest())
    out['status']='passed' if out['failed']==0 else 'failed'
    (BASE/'independent_verification.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k not in ('checks','hashes')}))
    assert out['status']=='passed'

if __name__=='__main__':main()
