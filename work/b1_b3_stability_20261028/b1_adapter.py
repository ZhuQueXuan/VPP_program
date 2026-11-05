"""Validated adapters around original B1 functions, keeping scientific cores frozen."""
import copy,math
import numpy as np
from core_io import ROOT,sha
from loaders import unique
from contracts import binary,integer,number,failed,result

def extract_event(t,reference,measured,t0,t1,q,dwell_samples=1,recovery_context='single_event'):
    try:
        if recovery_context not in ['single_event','shared_state_multiple_events']:raise ValueError('unknown recovery context')
        if not isinstance(t,(list,tuple,np.ndarray)) or len(t)<2:raise ValueError('time boundaries required')
        t=[number(x,'time') for x in t];t0=number(t0,'t0');t1=number(t1,'t1');q=number(q,'q',1e-12);integer(dwell_samples,'dwell_samples',1)
        if t0>=t1 or any(b<=a for a,b in zip(t,t[1:])):raise ValueError('increasing times/task required')
        def curve(v):
            if len(v)!=len(t)-1:raise ValueError('n interval powers and n+1 boundaries required')
            out=[]
            for x in v:
                if x is None:out.append(None)
                elif type(x) in (int,float) and not math.isfinite(x):out.append(None)
                else:out.append(number(x,'AC interval power'))
            return out
        reference=curve(reference);measured=curve(measured);f=unique('_stable_b1_f0','work/b1_research_20261021/features.py');v=f.extract(t,reference,measured,t0,t1,q,dwell_samples=dwell_samples)
        overlaps=[max(0,min(t[i+1],t1)-max(t[i],t0)) for i in range(len(reference))];cumulative=longest=run=0.
        for i,w in enumerate(overlaps):
            hit=w>0 and reference[i] is not None and measured[i] is not None and reference[i]-measured[i]>=.9*q
            if hit:cumulative+=w;run+=w;longest=max(longest,run)
            else:run=0.
        if recovery_context!='single_event':
            v.update(energy_recovery_status='not_identifiable_per_task_multiple_calls',energy_recovery_time_s=None,remaining_debt_kwh=None)
        return result('observed_event_features',dict(features=v,cumulative90_s=cumulative if v['Y'] is not None else None,continuous90_s=longest if v['Y'] is not None else None),
            units='s_kW_kWh',recovery_context=recovery_context,source_sha=sha(ROOT/'work/b1_research_20261021/features.py'),evidence='descriptive observed curve; threshold does not infer participation')
    except (ValueError,TypeError,KeyError,OverflowError) as e:return failed(e)

def fit_factor(x,w,d,a,outcomes,columns,minimum=20):
    try:
        fields=[binary(v,k) for v,k in zip([x,w,d,a],['X','W','D','A'])];n=len(fields[0]);integer(minimum,'minimum',1)
        if any(len(v)!=n for v in fields):raise ValueError('equal-length binary vectors required')
        y=np.asarray(outcomes)
        if y.shape!=(n,2) or y.dtype.kind not in 'iuf' or not np.isfinite(y).all():raise ValueError('finite n by2 observed outcomes required')
        if not isinstance(columns,list) or len(columns)!=len(set(columns)) or any(k not in ['X','W','A'] for k in columns):raise ValueError('unique declared adjustment columns required')
        m=unique('_stable_b1_est','work/b1_ev_factor_chain_20261026/estimators.py').fit(*fields,y,columns,minimum)
        return result('factor_model',dict(model=m),evidence='declared adjustment; A is diagnostic post-treatment control, never automatic identification',adjustment_role='diagnostic_post_treatment' if 'A' in columns else 'declared_pre_treatment')
    except (ValueError,TypeError,KeyError,IndexError,OverflowError) as e:return failed(e)

def predict_factor(model,x,w,a=None):
    try:
        x=binary(x,'X');w=binary(w,'W');aa=binary(a,'A') if a is not None else None
        if len(x)!=len(w) or (aa is not None and len(aa)!=len(x)):raise ValueError('equal-length queries required')
        if not isinstance(model,dict) or type(model.get('available')) is not bool:raise ValueError('factor model dictionary required')
        columns=model['columns']
        if not isinstance(columns,list) or any(k not in ['X','W','A'] for k in columns) or len(columns)!=len(set(columns)):raise ValueError('invalid model columns')
        if 'A' in columns and aa is None:raise ValueError('diagnostic model requires explicit A')
        if not model['available']:return dict(status='unavailable',reason='insufficient fitted support',committed_kw=None)
        table=np.asarray(model['table'])
        if table.shape!=(2,2**len(columns),2) or table.dtype.kind not in 'iuf' or not np.isfinite(table).all():raise ValueError('invalid factor table')
        p=unique('_stable_b1_est','work/b1_ev_factor_chain_20261026/estimators.py').predict(copy.deepcopy(model),x,w,aa)
        return result('conditional_outcome_means',dict(means=p.tolist()),evidence='not an individual capacity or participation probability')
    except (ValueError,TypeError,KeyError,IndexError,OverflowError) as e:return failed(e)

def learn_graph(data,minimum=20):
    try:
        a=binary(data,'graph nodes',2);integer(minimum,'minimum',1)
        if a.shape[1]!=5:raise ValueError('five columns X,W,D,A,S required')
        v=unique('_stable_b1_graph','work/b1_ev_factor_chain_20261026/graph.py').learn(a,minimum)
        return result('assumption_constrained_graph_screen',v,evidence='directions from declared order; not automatic causal identification')
    except (ValueError,TypeError,KeyError,IndexError,OverflowError) as e:return failed(e)
