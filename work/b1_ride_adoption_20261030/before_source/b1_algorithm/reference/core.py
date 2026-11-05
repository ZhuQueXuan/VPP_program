"""Versioned, pre-notice reference-power prediction for complete 1-minute data.

No simulator, ObsData, work-directory imports, pickle loading, response targets,
departure fields, or future-session imputation are used here.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import json
import math
import numbers
from typing import Sequence
import numpy as np
import lightgbm as lgb

SCHEMA_VERSION = 'b1-reference-v1'
FEATURE_NAMES = ('relative_midpoint_min','clock_hour','weekday','temperature_c',
                 'is_ev','notice_lead_min','pre60_kw','pre15_kw','prior_mean_kw')
PARAMS = dict(n_estimators=100,num_leaves=15,min_child_samples=35,learning_rate=.05,n_jobs=1,verbosity=-1)

@dataclass(frozen=True)
class ReferenceWindow:
    """All times use one caller-specified absolute minute origin.

    prior_mean_kw is a precomputed mean of >=2 completed, non-event historical
    curves, aligned by task-relative time. The caller must retain its source
    records; timestamps are checked but their factual provenance is not inferred.
    pre_power_kw contains ONLY intervals ending no later than notice_min.
    """
    task_id: str
    user_id: str
    meter_id: str
    resource_type: str
    task_start_min: float
    task_end_min: float
    request_kw: float
    notice_min: float
    starts_min: object
    ends_min: object
    pre_starts_min: object
    pre_ends_min: object
    pre_power_kw: object
    pre_available_min: float
    prior_mean_kw: object
    prior_available_min: float
    prior_source_count: int
    prior_source_ids: tuple[str,...]
    clock_hour: float
    weekday: int
    calendar_available_min: float
    temperature_c: float
    temperature_available_min: float
    prior_sources_non_event: bool = True

@dataclass(frozen=True)
class ReferenceTrainingRecord:
    window: ReferenceWindow
    target_power_kw: object
    target_available_min: float
    non_event: bool = True

@dataclass(frozen=True)
class WindowCalibrationRecord:
    window: ReferenceWindow
    observed_non_event_power_kw: object
    target_available_min: float
    non_event: bool = True

@dataclass
class ReferenceModel:
    booster: object
    model_id: str
    fit_cutoff_min: float
    seed: int
    training_users: tuple[str,...]
    training_records: tuple[str,...]
    training_digest: str
    calibration: dict = field(default_factory=dict)

@dataclass(frozen=True)
class ReferencePrediction:
    reference_status: str
    task_id: str
    user_id: str
    meter_id: str
    method: str
    model_id: str | None
    available_at_min: float | None
    starts_min: np.ndarray | None
    ends_min: np.ndarray | None
    reference_kw: np.ndarray | None
    reasons: tuple[str,...]
    role: str
    counterfactual_identified: bool = False
    window_band_eta: dict | None = None
    pointwise_noise_sigma_kw: None = None
    schema_version: str = SCHEMA_VERSION
    task_start_min: float | None = None
    task_end_min: float | None = None
    request_kw: float | None = None
    notice_min: float | None = None

def _number(value,name):
    if isinstance(value,(bool,np.bool_)) or not isinstance(value,numbers.Real):
        raise ValueError(name+' must be a finite real number, not bool/string')
    try:number=float(value)
    except (OverflowError,ValueError):raise ValueError(name+' outside finite numeric range')
    if not math.isfinite(number):raise ValueError(name+' must be finite')
    return number

def _integer(value,name):
    number=_number(value,name)
    if number!=math.floor(number):raise ValueError(name+' must be an integer')
    return int(number)

def _identifier(value,name):
    if not isinstance(value,str) or not value.strip():raise ValueError(name+' must be a nonempty string')
    return value

def _array(value,name):
    original=np.asarray(value,dtype=object)
    if original.ndim!=1 or not len(original):
        raise ValueError(name+' must be a nonempty finite numeric vector')
    # Check before NumPy promotes mixed [True,1.2] or ['1',2] containers.
    if any(isinstance(v,(bool,np.bool_)) or not isinstance(v,numbers.Real) for v in original):
        raise ValueError(name+' cannot contain bool/string/non-real elements')
    try:a=np.asarray(value,float)
    except (ValueError,TypeError,OverflowError):raise ValueError(name+' outside finite numeric range')
    if not np.isfinite(a).all():raise ValueError(name+' must be finite')
    return a

def _float32(value,name):
    a=_array(value,name)
    if np.any(np.abs(a)>np.finfo('float32').max):raise ValueError(name+' outside finite float32 feature range')
    return a.astype('float32')

def _grid(starts,ends,name):
    s,e=_array(starts,name+'_starts'),_array(ends,name+'_ends')
    if len(s)>270:raise ValueError(name+' exceeds finite 270-bin domain')
    if s.shape!=e.shape or not np.allclose(e-s,1.,rtol=0,atol=1e-9):
        raise ValueError(name+' requires complete one-minute intervals')
    if len(s)>1 and not np.allclose(s[1:],e[:-1],rtol=0,atol=1e-9):
        raise ValueError(name+' intervals must be ordered, contiguous and nonoverlapping')
    return s,e

def _validated(window):
    if not isinstance(window,ReferenceWindow):raise ValueError('ReferenceWindow required')
    for name in ('task_id','user_id','meter_id'):_identifier(getattr(window,name),name)
    task=_number(window.task_start_min,'task_start_min')
    end=_number(window.task_end_min,'task_end_min')
    notice=_number(window.notice_min,'notice_min')
    request=_number(window.request_kw,'request_kw')
    if end<=task or request<=0 or notice>=task:raise ValueError('positive task, request and notice lead required')
    if not any(np.isclose(end-task,v,atol=1e-8,rtol=0) for v in (30.,60.)):
        raise ValueError('reference task duration domain is30/60 minutes')
    s,e=_grid(window.starts_min,window.ends_min,'prediction')
    if s[0]<task-120-1e-9 or e[-1]>task+90+1e-9:
        raise ValueError('reference domain is task-relative[-120,90] minutes')
    if s[0]>task+1e-9 or e[-1]<end-1e-9:raise ValueError('prediction grid must contain task window')
    if not np.any(np.isclose(s,task,rtol=0,atol=1e-9)) or not np.any(np.isclose(e,end,rtol=0,atol=1e-9)):
        raise ValueError('task boundaries must align with complete intervals')
    ps,pe=_grid(window.pre_starts_min,window.pre_ends_min,'prefix')
    if np.any(pe>notice+1e-9):raise ValueError('post-notice power forbidden in prefix')
    p=_float32(window.pre_power_kw,'pre_power_kw')
    if p.shape!=ps.shape:raise ValueError('prefix power/grid shape mismatch')
    # Preserve the validated SafeGBDT masked-sum arithmetic on its canonical
    # [-120,90] analysis grid. This also makes prefix statistics independent
    # of the requested prediction subgrid. No future measurements are read.
    full_starts=task+np.arange(-120.,90.)
    ix=np.rint(ps-task+120).astype(int)
    if np.any(ix<0) or np.any(ix>=len(full_starts)):
        raise ValueError('prefix outside task-relative[-120,90] minute domain')
    if not np.allclose(full_starts[ix],ps,atol=1e-9,rtol=0):
        raise ValueError('prefix and prediction grids must use the same minute lattice')
    full_power=np.zeros(len(full_starts),dtype='float32');full_power[ix]=p
    def past_mean(minutes):
        use=(ps>=notice-minutes-1e-9)&(pe<=notice+1e-9)
        if use.sum()!=minutes or not np.isclose(ps[use][0],notice-minutes,rtol=0,atol=1e-9) or not np.isclose(pe[use][-1],notice,rtol=0,atol=1e-9):
            raise ValueError('complete '+str(minutes)+' minute pre-notice history required')
        full_use=(full_starts>=notice-minutes-1e-9)&(full_starts+1<=notice+1e-9)
        return float(np.where(full_use,full_power,0.).sum())/int(use.sum())
    mean60,mean15=past_mean(60),past_mean(15)
    prior=_float32(window.prior_mean_kw,'prior_mean_kw')
    if prior.shape!=s.shape:raise ValueError('prior mean/prediction grid shape mismatch')
    count=_integer(window.prior_source_count,'prior_source_count')
    if count<2:raise ValueError('at least two historical prior sources required')
    if not isinstance(window.prior_source_ids,(list,tuple)) or len(window.prior_source_ids)!=count:
        raise ValueError('historical source IDs/count mismatch')
    for source in window.prior_source_ids:_identifier(source,'historical source ID')
    if len(set(window.prior_source_ids))!=count or window.task_id in window.prior_source_ids:
        raise ValueError('historical source IDs must be unique and exclude current task')
    if window.prior_sources_non_event is not True:raise ValueError('prior sources must be declared non-event')
    for name in ('pre_available_min','prior_available_min','calendar_available_min','temperature_available_min'):
        if _number(getattr(window,name),name)>notice+1e-9:raise ValueError(name+' is later than notice')
    hour=_number(window.clock_hour,'clock_hour')
    weekday=_integer(window.weekday,'weekday')
    temperature=_number(window.temperature_c,'temperature_c')
    if not 0<=hour<24 or not 0<=weekday<=6:raise ValueError('calendar value outside supported range')
    lead=task-notice
    supported=[v for v in (15.,30.,60.) if np.isclose(lead,v,atol=1e-8,rtol=0)]
    if not supported:raise ValueError('supported notice leads:15/30/60 minutes')
    lead=supported[0]
    return dict(s=s,e=e,prefix_mean60=mean60,prefix_mean15=mean15,prior=prior,
                task=task,end=end,notice=notice,request=request,hour=hour,weekday=weekday,temp=temperature,lead=lead)

def feature_matrix(window):
    a=_validated(window)
    resource=window.resource_type
    if resource not in ('EV','AC'):raise ValueError('resource_type must be EV or AC')
    n=len(a['s'])
    const=lambda x:np.full(n,x)
    result=np.column_stack([(a['s']+a['e'])/2-a['task'],const(a['hour']),const(a['weekday']),
                            const(a['temp']),const(resource=='EV'),const(a['lead']),
                            const(a['prefix_mean60']),const(a['prefix_mean15']),a['prior']])
    if not np.isfinite(result).all() or np.any(np.abs(result)>np.finfo('float32').max):
        raise ValueError('feature outside finite float32 range')
    return result.astype('float32')

def fit_reference(records:Sequence[ReferenceTrainingRecord],fit_cutoff_min,seed=0):
    cutoff=_number(fit_cutoff_min,'fit_cutoff_min');seed=_integer(seed,'seed')
    if not 0<=seed<2**31:raise ValueError('seed outside supported nonnegative int32 range')
    if not records:raise ValueError('training records required')
    rng=np.random.default_rng(seed);xs=[];ys=[];users=set();ids=[];digest=hashlib.sha256()
    for record in records:
        if not isinstance(record,ReferenceTrainingRecord) or record.non_event is not True:
            raise ValueError('historical non-event training records required')
        w=record.window;x=feature_matrix(w);y=_float32(record.target_power_kw,'training target')
        if len(y)!=len(x):raise ValueError('training target/grid shape mismatch')
        available=_number(record.target_available_min,'target_available_min')
        if available>cutoff+1e-9 or available<float(np.max(w.ends_min))-1e-9:
            raise ValueError('target must be completed and available by fit cutoff')
        if cutoff<w.notice_min:raise ValueError('training features unavailable at fit cutoff')
        if w.task_id in ids:raise ValueError('duplicate historical training task_id')
        kk=rng.integers(0,len(y),16);xx=x[kk];yy=y[kk]
        xs.append(xx);ys.append(yy);users.add(w.user_id);ids.append(w.task_id)
        digest.update(xx.tobytes());digest.update(yy.tobytes());digest.update(w.task_id.encode('utf-8'))
    x=np.concatenate(xs);y=np.concatenate(ys)
    reg=lgb.LGBMRegressor(random_state=seed,**PARAMS).fit(x,y)
    booster=reg.booster_
    model_text=booster.model_to_string()
    model_id='ref-'+hashlib.sha256(model_text.encode()).hexdigest()[:20]
    return ReferenceModel(booster,model_id,cutoff,seed,tuple(sorted(users)),tuple(ids),digest.hexdigest())

def _unavailable(window,method,model,reason,role='unknown'):
    return ReferencePrediction('unavailable',str(getattr(window,'task_id','')),str(getattr(window,'user_id','')),
        str(getattr(window,'meter_id','')),method,getattr(model,'model_id',None),None,None,None,None,(reason,),role)

def predict_reference(model,window,method='gbdt',allow_seen_user=False):
    """Default held-out prediction rejects training/calibration users.

    allow_seen_user=True enables operational predictions from legal past data;
    the result is explicitly labelled seen-user and cannot be counted as a
    held-out-user evaluation. It does not permit post-notice inputs.
    """
    try:
        if type(allow_seen_user) is not bool:raise ValueError('allow_seen_user must be bool')
        x=feature_matrix(window);a=_validated(window)
        if method not in ('gbdt','prev10'):raise ValueError('unknown reference method')
        if method=='gbdt' and not isinstance(model,ReferenceModel):raise ValueError('fitted ReferenceModel required')
        role='unseen_user'
        if model is not None:
            if model.fit_cutoff_min>a['notice']+1e-9:raise ValueError('model fitted after query notice')
            if window.user_id in model.training_users:role='seen_training_user'
            elif window.user_id in model.calibration.get('users',[]):role='seen_calibration_user'
            if role!='unseen_user' and not allow_seen_user:raise ValueError('held-out prediction forbids training/calibration user overlap')
        prediction=model.booster.predict(x) if method=='gbdt' else a['prior'].astype(float)
        if not np.isfinite(prediction).all():raise ValueError('nonfinite model prediction')
        for ar in (a['s'],a['e'],prediction):ar.setflags(write=False)
        band=None
        if model is not None and method=='gbdt' and model.calibration:
            cal=model.calibration
            if cal['cutoff_min']>a['notice']+1e-9:raise ValueError('calibration completed after query notice')
            width=cal['by_resource'].get(window.resource_type,{}).get('halfwidth_eta')
            band=dict(halfwidth_eta=width,alpha=cal['alpha'],scope='whole-task-window normalized residual; user-block pseudo-event calibration',
                      transferable_to_actual_counterfactual=False,pointwise_sigma=False)
        return ReferencePrediction('available',window.task_id,window.user_id,window.meter_id,method,
            getattr(model,'model_id',None),a['notice'],a['s'],a['e'],prediction,(),role,window_band_eta=band,
            task_start_min=a['task'],task_end_min=a['end'],request_kw=a['request'],notice_min=a['notice'])
    except (ValueError,TypeError,AttributeError) as exc:
        return _unavailable(window,method,model,str(exc))

def calibrate_window_reference(model,records:Sequence[WindowCalibrationRecord],cutoff_min,alpha=.1):
    if not isinstance(model,ReferenceModel):raise ValueError('ReferenceModel required')
    cutoff=_number(cutoff_min,'calibration cutoff');alpha=_number(alpha,'alpha')
    if not 0<alpha<1 or cutoff<model.fit_cutoff_min:raise ValueError('invalid calibration alpha/cutoff')
    by_user={};resources={};ids=set()
    for record in records:
        if not isinstance(record,WindowCalibrationRecord) or record.non_event is not True:
            raise ValueError('independent non-event calibration records required')
        w=record.window
        if w.task_id in ids:raise ValueError('duplicate calibration task_id')
        ids.add(w.task_id)
        if w.user_id in model.training_users:raise ValueError('training and calibration users overlap')
        if w.user_id in resources and resources[w.user_id]!=w.resource_type:raise ValueError('one calibration user has multiple resource types')
        resources[w.user_id]=w.resource_type
        pred=predict_reference(model,w)
        if pred.reference_status!='available':raise ValueError('invalid calibration prediction: '+','.join(pred.reasons))
        y=_array(record.observed_non_event_power_kw,'calibration power')
        if y.shape!=pred.reference_kw.shape:raise ValueError('calibration power shape mismatch')
        available=_number(record.target_available_min,'calibration target available')
        if available>cutoff+1e-9 or available<float(np.max(w.ends_min))-1e-9:raise ValueError('calibration label not completed by cutoff')
        use=(pred.starts_min>=w.task_start_min-1e-9)&(pred.ends_min<=w.task_end_min+1e-9)
        score=abs(float(np.mean(pred.reference_kw[use]-y[use]))/w.request_kw)
        by_user[w.user_id]=max(by_user.get(w.user_id,0.),score)
    summaries={}
    for resource in ('EV','AC'):
        scores=sorted(v for u,v in by_user.items() if resources[u]==resource)
        rank=math.ceil((len(scores)+1)*(1-alpha))
        summaries[resource]=dict(n_users=len(scores),rank=rank,halfwidth_eta=float(scores[rank-1]) if 0<rank<=len(scores) else None)
    model.calibration=dict(alpha=alpha,cutoff_min=cutoff,users=sorted(by_user),by_resource=summaries,
                           score='max absolute normalized window residual per calibration user')
    return model

def save_reference_model(model,directory):
    if not isinstance(model,ReferenceModel):raise ValueError('ReferenceModel required')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    model_path=directory/'model.txt';meta_path=directory/'metadata.json'
    if model_path.exists() or meta_path.exists():raise ValueError('artifact files already exist; choose a new directory')
    model.booster.save_model(str(model_path))
    metadata=dict(schema_version=SCHEMA_VERSION,feature_names=list(FEATURE_NAMES),params=PARAMS,
        lightgbm_version=lgb.__version__,model_id=model.model_id,fit_cutoff_min=model.fit_cutoff_min,seed=model.seed,
        training_users=list(model.training_users),training_records=list(model.training_records),training_digest=model.training_digest,
        calibration=model.calibration,model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),
        model_format='LightGBM native text; no pickle',time_unit='caller absolute minutes with one consistent origin')
    meta_path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    return metadata

def load_reference_model(directory):
    directory=Path(directory);mp=directory/'model.txt';jp=directory/'metadata.json'
    if not mp.is_file() or not jp.is_file() or mp.stat().st_size>20_000_000 or jp.stat().st_size>1_000_000:
        raise ValueError('missing or oversized local artifact files')
    m=json.loads(jp.read_text(encoding='utf-8'))
    expected_fields={'schema_version','feature_names','params','lightgbm_version','model_id','fit_cutoff_min','seed',
                     'training_users','training_records','training_digest','calibration','model_sha256','model_format','time_unit'}
    if not isinstance(m,dict) or set(m)!=expected_fields:raise ValueError('artifact metadata fields mismatch')
    if m.get('schema_version')!=SCHEMA_VERSION or m.get('feature_names')!=list(FEATURE_NAMES) or m.get('params')!=PARAMS:
        raise ValueError('artifact schema/features/parameters mismatch')
    if m.get('lightgbm_version')!=lgb.__version__:raise ValueError('LightGBM version mismatch')
    if hashlib.sha256(mp.read_bytes()).hexdigest()!=m.get('model_sha256'):raise ValueError('artifact model SHA mismatch')
    cutoff=_number(m.get('fit_cutoff_min'),'artifact fit cutoff');seed=_integer(m.get('seed'),'artifact seed')
    users=m.get('training_users');ids=m.get('training_records')
    if not isinstance(users,list) or not isinstance(ids,list) or not users or not ids:
        raise ValueError('artifact user/record fields invalid')
    for u in users:_identifier(u,'artifact user')
    for r in ids:_identifier(r,'artifact record')
    if len(set(users))!=len(users) or len(set(ids))!=len(ids):raise ValueError('artifact duplicate user/record fields')
    if not 0<=seed<2**31:raise ValueError('artifact seed out of range')
    booster=lgb.Booster(model_file=str(mp))
    if booster.num_feature()!=len(FEATURE_NAMES):raise ValueError('artifact native feature count mismatch')
    expected='ref-'+hashlib.sha256(booster.model_to_string().encode()).hexdigest()[:20]
    if expected!=m.get('model_id'):raise ValueError('artifact model_id mismatch')
    calibration=m.get('calibration',{})
    if not isinstance(calibration,dict):raise ValueError('artifact calibration field invalid')
    if calibration:
        if set(calibration)!={'alpha','cutoff_min','users','by_resource','score'}:raise ValueError('artifact calibration fields mismatch')
        alpha=_number(calibration['alpha'],'artifact calibration alpha')
        cc=_number(calibration['cutoff_min'],'artifact calibration cutoff')
        if not 0<alpha<1 or cc<cutoff:raise ValueError('artifact calibration alpha/cutoff invalid')
        cu=calibration['users']
        if not isinstance(cu,list) or len(set(cu))!=len(cu) or set(cu)&set(users):raise ValueError('artifact calibration user roles invalid')
        for u in cu:_identifier(u,'artifact calibration user')
        by=calibration['by_resource']
        if not isinstance(by,dict) or set(by)!={'EV','AC'}:raise ValueError('artifact calibration resources invalid')
        total=0
        for entry in by.values():
            if not isinstance(entry,dict) or set(entry)!={'n_users','rank','halfwidth_eta'}:raise ValueError('artifact calibration summary invalid')
            n=_integer(entry['n_users'],'artifact calibration user count')
            rank=_integer(entry['rank'],'artifact calibration rank')
            if n<0 or rank!=math.ceil((n+1)*(1-alpha)):raise ValueError('artifact calibration rank invalid')
            width=entry['halfwidth_eta']
            if width is not None and _number(width,'artifact window halfwidth')<0:raise ValueError('artifact calibration width invalid')
            if rank>n and width is not None:raise ValueError('artifact insufficient calibration must have null width')
            total+=n
        if total!=len(cu):raise ValueError('artifact calibration total mismatch')
    return ReferenceModel(booster,expected,cutoff,seed,tuple(users),tuple(ids),str(m.get('training_digest','')),calibration)
