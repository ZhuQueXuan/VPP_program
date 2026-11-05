"""CPOP blocks plus a finite dictionary of optional free level/slope resets.

No values or weights are changed. Inside each block the native continuous CPOP
fit is retained. The outer exact DP allows discontinuity at candidate bin edges.
This is NOT GRACE's general recursion or a slope-preserving jump estimator.
"""
from common import *
from numbers import Real
from concurrent.futures import ThreadPoolExecutor,as_completed
VERSION='cpop-finite-jump-block-v2'
def numeric(v):
    a=np.asarray(v,dtype=object)
    if a.ndim!=1 or any(isinstance(x,(bool,np.bool_)) or not isinstance(x,Real) for x in a):raise ValueError('finite numeric1d required')
    b=np.asarray(v,dtype=float)
    if not np.isfinite(b).all():raise ValueError('nonfinite input')
    return b
def propose_edges(y,x,sigma,command,top=6):
    y=numeric(y);x=numeric(x);command=numeric(command)
    if y.shape!=x.shape or command.shape!=y.shape or len(y)<3 or np.any(np.diff(x)<=0):raise ValueError('matching ordered observations and command required')
    if not isinstance(sigma,Real) or isinstance(sigma,(bool,np.bool_)) or not np.isfinite(sigma) or sigma<=0:raise ValueError('positive finite sigma required')
    if top!=6:raise ValueError('fixed candidate budget is6')
    n=len(y);pitch=float(np.median(np.diff(x)));records=[]
    for j in range(1,n):
        boundary=(x[j-1]+x[j])/2;scores=[]
        for width in (1,2,4):
            if j<width or j+width>n:continue
            if width==1:
                left,right=float(y[j-1]),float(y[j]);variance=2.
            else:
                def at_edge(indices):
                    A=np.column_stack([np.ones(len(indices)),(x[indices]-boundary)/pitch])
                    G=np.linalg.inv(A.T@A);coef=G@A.T@y[indices]
                    return float(coef[0]),float(G[0,0])
                left,vl=at_edge(np.arange(j-width,j));right,vr=at_edge(np.arange(j,j+width));variance=vl+vr
            scores.append({'width':width,'score':abs(right-left)/(sigma*np.sqrt(variance))})
        records.append({'index':j,'score':max(v['score'] for v in scores),'scales':scores})
    ranked=sorted(records,key=lambda r:(-r['score'],r['index']))
    observational=[r['index'] for r in ranked[:min(top,n-1)]]
    command_edges=(np.flatnonzero(np.abs(np.diff(command))>1e-12)+1).tolist()
    edges=sorted(set(observational+command_edges))
    return {'version':VERSION,'nodes':[0]+edges+[n],'edges':edges,'observational_edges':observational,
        'command_edges':command_edges,'all_boundary_scores':records,'top_budget':top,
        'values_and_weights_unchanged':True,'actual_jump_required_at_command':False,
        'time_unit_inherited_from_input':True}
def _cache_chunk(cases,directory):
    out=HERE/directory;out.mkdir(parents=True,exist_ok=False)
    with (out/'input.csv').open('x',encoding='utf-8',newline='') as h:
        w=csv.writer(h);w.writerow(['case_id','index','x','y','sigma','beta'])
        for c in cases:w.writerows((c['case_id'],j,float(x),float(y),c['sigma'],2*np.log(len(c['y']))) for j,(x,y) in enumerate(zip(c['x'],c['y'])))
    mapping={};blockid=0
    with (out/'blocks.csv').open('x',encoding='utf-8',newline='') as h:
        w=csv.writer(h);w.writerow(['block_id','case_id','a','b'])
        for c in cases:
            nodes=c['proposal']['nodes']
            for i,a in enumerate(nodes[:-1]):
                for b in nodes[i+1:]:
                    mapping[blockid]=(c['case_id'],int(a),int(b));w.writerow([blockid,c['case_id'],a,b]);blockid+=1
    meta=call_r('blocks_batch.R',[out/'input.csv',out/'blocks.csv',out/'segments.csv',runtime('unused')['r_library']],directory+'/run')
    groups={}
    with (out/'segments.csv').open(encoding='utf-8-sig',newline='') as h:
        for r in csv.DictReader(h):groups.setdefault(int(r['block_id']),[]).append(r)
    case_lookup={c['case_id']:c for c in cases};result={c['case_id']:{} for c in cases}
    for bid,(cid,a,b) in mapping.items():
        rows=groups.get(bid,[])
        if not rows or any(r['status']!='ok' for r in rows):
            result[cid][f'{a}:{b}']={'status':'unavailable','reason':rows[0]['error'] if rows else 'missing_block'};continue
        x=np.asarray(case_lookup[cid]['x'])[a:b];pred=np.full(b-a,np.nan)
        segments=[r for r in rows if float(r['x1'])>float(r['x0'])]
        if b-a==1:pred[:]=float(rows[0]['intercept'])
        else:
            for j,r in enumerate(segments):
                lo,hi=float(r['x0']),float(r['x1']);mask=(x>=lo-1e-9)&(x<=hi+1e-9)
                if j==0:mask|=x<lo
                if j==len(segments)-1:mask|=x>hi
                pred[mask]=float(r['gradient'])*x[mask]+float(r['intercept'])
        if not np.isfinite(pred).all():
            result[cid][f'{a}:{b}']={'status':'unavailable','reason':'nonfinite_block_prediction'};continue
        result[cid][f'{a}:{b}']={'status':'ok','prediction':pred,'cost':float(rows[0]['native_cost']),
             'internal_knots':int(rows[0]['internal_knots']),'n_points':b-a,'seconds':float(rows[0]['seconds']),
             'beta':float(rows[0]['beta']),'sigma':float(rows[0]['sigma'])}
    return result,meta
def cache_blocks(cases,directory,chunk_size=48):
    result={};meta=[];chunks=[cases[j:j+chunk_size] for j in range(0,len(cases),chunk_size)]
    start=time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(_cache_chunk,c,f'{directory}/chunk_{j:03d}'):j for j,c in enumerate(chunks)}
        for f in as_completed(futures):
            r,m=f.result();result.update(r);meta.append(m)
            print('native block chunks',len(meta),'/',len(chunks),flush=True)
    return result,{'wall_seconds':time.perf_counter()-start,'chunks':meta,'workers':4,'not_exclusive_single_case_latency':True}
def choose_partition(proposal,cache,sigma,n,penalty_ratio):
    if penalty_ratio not in (1.,1.5,2.):raise ValueError('outside frozen family')
    nodes=proposal['nodes'];beta=2*np.log(n);jump_cost=penalty_ratio*beta
    if nodes[0]!=0 or nodes[-1]!=n or any(b<=a for a,b in zip(nodes,nodes[1:])):raise ValueError('invalid nodes')
    for j,b in enumerate(nodes[1:],1):
        for a in nodes[:j]:
            r=cache.get(f'{a}:{b}')
            if r is None or r['status']!='ok':return {'status':'unavailable','reason':'incomplete_block_dictionary','prediction':None,'version':VERSION}
            if not np.isclose(r['beta'],beta,rtol=0,atol=1e-10) or not np.isclose(r['sigma'],sigma,rtol=0,atol=1e-12):raise ValueError('block condition mismatch')
    best=[None]*len(nodes);best[0]={'cost':0.,'path':[0],'jumps':0}
    for j in range(1,len(nodes)):
        candidates=[]
        for i in range(j):
            before=best[i];score=before['cost']+cache[f'{nodes[i]}:{nodes[j]}']['cost']+(jump_cost if i>0 else 0.)
            path=before['path']+[nodes[j]]
            candidates.append({'cost':float(score),'path':path,'jumps':len(path)-2})
        minimum=min(r['cost'] for r in candidates);tol=1e-10*max(1.,abs(minimum))
        best[j]=min((r for r in candidates if r['cost']<=minimum+tol),key=lambda r:(r['jumps'],tuple(r['path'])))
    chosen=best[-1];pred=np.empty(n);inside=0
    for a,b in zip(chosen['path'],chosen['path'][1:]):
        block=cache[f'{a}:{b}'];pred[a:b]=block['prediction'];inside+=block['internal_knots']
    baseline=cache[f'0:{n}']['cost']
    assert chosen['cost']<=baseline+1e-7*max(1.,abs(baseline))
    return {'status':'ok','prediction':pred,'version':VERSION,'penalty_ratio':float(penalty_ratio),
       'objective':chosen['cost'],'original_family_cost':baseline,'jump_boundaries':chosen['path'][1:-1],
       'selected_blocks':[[a,b] for a,b in zip(chosen['path'],chosen['path'][1:])],
       'internal_slope_changes':inside,'jump_cost':float(jump_cost),'beta':float(beta),
       'values_and_weights_unchanged':True,'zero_jump_CPOP_included':True,
       'exactness':'unpruned finite candidate-boundary partition with native CPOP block optima; not all-position mixed-transition GRACE',
       'jump_type':'free reset of both level and slope; incoming slope not preserved',
       'physical_subbin_timing_identified':False,'single_point_sensor_fault_disambiguated':False}
