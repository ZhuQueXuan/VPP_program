"""Independent extraction/area/availability/DP verification, no study imports."""
from pathlib import Path
from itertools import product
import json,hashlib,math,csv
import numpy as np
from scipy.special import ndtri
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
RAW=ROOT/'data/驱动因素解耦模拟数据集_B1_fullcycle_features_v1_20261026'
CHECKS=[];MAXERR={}
def check(name,ok):CHECKS.append(dict(name=name,passed=bool(ok)))
def close(name,a,b,tol=1e-10):
    a,b=np.asarray(a),np.asarray(b);finite=np.isfinite(a)&np.isfinite(b)
    err=float(np.max(abs(a[finite]-b[finite]))) if finite.any() else 0.
    MAXERR[name]=max(MAXERR.get(name,0),err)
    check(name,np.array_equal(np.isfinite(a),np.isfinite(b)) and err<tol)
def same(name,a,b):
    if a is None or b is None:check(name,a is b)
    elif isinstance(b,(float,np.floating)):close(name,a,b)
    else:check(name,a==b)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def characterize(y,dt,obs):
    """Convolution run windows; independent of old _run and main evaluator."""
    y=np.asarray(y);d=max(1,math.ceil(30/dt));a=600//dt;b=1800//dt;n=len(y)
    def hit(mask,left,right):
        # Window convolution uses only finite samples already encoded in mask.
        windows=np.convolve(mask[left:right].astype(int),np.ones(d,int),'valid')
        hit=np.flatnonzero(windows==d)
        return float((left+hit[0])*dt) if len(hit) else None
    valid=np.isfinite(y);onset=hit(valid&(y>=.15),a,b);target=hit(valid&(y>=1.35),a,b)
    mask=valid[a:b]&(y[a:b]>=.15);edges=np.diff(np.r_[0,mask.astype(int),0]);lengths=np.flatnonzero(edges==-1)-np.flatnonzero(edges==1)
    longest=int(max(lengths,default=0));duration=float(longest*dt) if longest>=d else 0.
    recovery=hit(valid&(abs(y)<=.15),b,n) if onset is not None else None
    status='not_applicable' if onset is None else ('recovered' if recovery is not None else 'right_censored')
    stage='no_response' if onset is None else ('partial' if target is None else 'response')
    confirm=None if onset is None else onset+d*dt
    if obs=='missing_request':stage=status='unavailable';onset=target=recovery=confirm=duration=None
    if obs=='missing_post':status='unavailable';recovery=None
    return dict(stage=stage,onset_s=onset,onset_confirmation_s=confirm,target_s=target,duration_s=duration,power_recovery_status=status,power_recovery_s=recovery)

def independent_dp(y,penalty,dwell):
    """Direct two-pass segment residuals, no prefix subtraction or main module."""
    n=len(y);cost=[float('inf')]*(n+1);last=[-1]*(n+1);cost[0]=-penalty
    for end in range(dwell,n+1):
        for start in range(end-dwell+1):
            if not math.isfinite(cost[start]):continue
            chunk=y[start:end];mean=math.fsum(chunk)/len(chunk)
            val=cost[start]+math.fsum((v-mean)**2 for v in chunk)+penalty
            if val<cost[end]:cost[end]=val;last[end]=start
    fit=np.empty(n);end=n
    while end:
        start=last[end];fit[start:end]=math.fsum(y[start:end])/(end-start);end=start
    return fit,cost[n]

def main():
    p=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))
    idx=json.loads((RAW/'observation_index.json').read_text(encoding='utf-8'))
    pred=json.loads((BASE/'predictions.json').read_text(encoding='utf-8'))
    truth=json.loads((BASE/'evaluation_truth.json').read_text(encoding='utf-8'))
    meta=json.loads((BASE/'hidden_meta.json').read_text(encoding='utf-8'))
    raw=np.load(RAW/'observations.npz');power=raw['power_obs_kw'];hidden=np.load(BASE/'hidden_native.npz')['reduction_kw'];fits=np.load(BASE/'fitted_reductions.npz')['reduction_kw']
    receipt=json.loads((BASE/'extraction_receipt.json').read_text(encoding='utf-8'))
    check('all output/data shapes',len(idx)==2400 and len(pred)==4800 and power.shape==(2400,360) and hidden.shape==(150,360) and fits.shape==(4800,360))
    check('observations contain no hidden signal',set(raw.files)=={'power_obs_kw','reference_kw'})
    for file,key,folder in [('observations.npz','raw_sha256',RAW),('predictions.json','predictions_sha256',BASE),('fitted_reductions.npz','fits_sha256',BASE)]:check('persisted identity '+file,sha(folder/file)==receipt[key])
    lookup={(v['rep'],v['mechanism'],v['sigma_native_kw'],v['dt_s'],v['observation']):i for i,v in enumerate(idx)}
    for lid,h in enumerate(hidden):
        check('latent full energy and power constraints',abs(math.fsum(h)*10)<1e-8 and np.all((3-h>=0)&(3-h<=6)))
        debt=math.fsum(h[60:180])*10
        check('post repayment independent area',abs(math.fsum(h[180:])*10+debt)<1e-8)
        m=meta[lid];t=np.arange(360)*10;expected=np.zeros(120);tt=t[60:180];active=tt>=600+m['delay_s']
        if m['mechanism']=='step':expected[active]=1.5
        elif m['mechanism']=='partial':expected[active]=m['partial_kw']
        elif m['mechanism']=='slow_ramp':expected[active]=np.minimum((tt[active]-600-m['delay_s'])/600,1)*1.5
        elif m['mechanism']=='early_exit':expected[active&(tt<m['early_end_s'])]=1.5
        elif m['mechanism']=='interrupted':expected[active&~((tt>=m['drop_start_s'])&(tt<m['drop_start_s']+m['drop_duration_s']))]=1.5
        close('declared request mechanism reconstruction',h[60:180],expected)
    with (BASE/'metrics.csv').open(encoding='utf-8-sig',newline='') as f:metrics=list(csv.DictReader(f))
    check('all metric rows retained',len(metrics)==4800)
    for i,v in enumerate(idx):
        n=v['n'];dt=v['dt_s'];factor=dt//10;end=v['end_s'];obs=v['observation'];a=600//dt;b=1800//dt;sig=v['sigma_effective_kw']
        y=3-power[i,:n];native=hidden[v['latent_id']];latent=np.array([math.fsum(native[j:j+factor])/factor for j in range(0,n*factor,factor)])
        # Observation pairing, resampling and missing masks.
        fullnative=power[lookup[v['rep'],v['mechanism'],v['sigma_native_kw'],10,'full'],:360]
        reconstructed=np.array([math.fsum(fullnative[j:j+factor])/factor for j in range(0,n*factor,factor)])
        if obs.startswith('missing_'):
            lo,hi=p['grid'][obs];reconstructed[(np.arange(n)*dt>=lo)&(np.arange(n)*dt<hi)]=np.nan
        close('coarse/missing/short observation identity',power[i,:n],reconstructed)
        check('padding not interpreted as missing samples',np.isnan(power[i,n:]).all())
        close('effective sigma from averaging',sig,v['sigma_native_kw']/math.sqrt(factor))
        criterion=characterize(latent,dt,obs)
        for key in ('stage','onset_s','target_s','duration_s','power_recovery_status','power_recovery_s'):same('independent truth '+key,truth[i][key],criterion[key])
        trueenergy=None if obs=='missing_request' else math.fsum(latent[a:b])*dt/3600
        truedebt=None if obs.startswith('missing_') else math.fsum(latent[a:])*dt/3600
        same('true request area',truth[i]['request_net_kwh'],trueenergy);same('true observed-end debt',truth[i]['debt_kwh'],truedebt)
        for mi in (0,1):
            out=pred[2*i+mi];fit=fits[2*i+mi,:n];mr=metrics[2*i+mi]
            expected=characterize(fit,dt,obs)
            for key,val in expected.items():same('output '+key,out[key],val)
            if mi==0:close('F0 consumes unchanged raw reduction',fit,y)
            check('F1 never bridges gap',np.array_equal(np.isfinite(fit),np.isfinite(y)))
            energy=None if obs=='missing_request' else math.fsum(y[a:b])*dt/3600
            same('both methods original observed energy',out['request_net_kwh'],energy)
            same('fixed signed Y',out['Y'],None if energy is None else energy*2)
            close('coverage',out['request_coverage'],np.isfinite(y[a:b]).sum()/(b-a))
            bal=out['balance']
            if obs.startswith('missing_'):
                check('missing energy explicitly unavailable',bal['status']=='unavailable' and all(bal[k] is None for k in ('debt_kwh','lower_kwh','upper_kwh')))
            else:
                debt=math.fsum(y[a:])*dt/3600;half=ndtri(.975)*sig*math.sqrt((n-a)*dt*dt)/3600
                close('raw signed debt',bal['debt_kwh'],debt);close('energy lower',bal['lower_kwh'],debt-half);close('energy upper',bal['upper_kwh'],debt+half)
                st='right_censored' if end<3600 else ('within_margin' if debt+half<=.01 else 'above_margin' if debt-half>.01 else 'unresolved')
                check('energy decision/censoring',bal['status']==st)
            # Every primary metric rederived from independently checked estimates/truth.
            for key in ('onset_s','target_s','duration_s','power_recovery_s','request_net_kwh'):
                t=truth[i][key];est=out[key];err=None if t is None or est is None else est-t
                for col,expectedval in [('true_'+key,t),('estimated_'+key,est),(key+'_error',err)]:same('metric '+col,None if mr[col]=='' else float(mr[col]),expectedval)
                if key.endswith('_s'):
                    check('unconditional within30 denominator',mr[key+'_within30']==str(bool(t is not None and est is not None and abs(est-t)<=30)))
            close('curve MSE independent',float(mr['curve_mse_kw2']),np.mean((fit[np.isfinite(y)]-latent[np.isfinite(y)])**2))
            for col,expectedval in [('stage_correct',out['stage']==truth[i]['stage']),('power_status_correct',out['power_recovery_status']==truth[i]['power_recovery_status']),('onset_false_detection',truth[i]['stage']=='no_response' and out['onset_s'] is not None),('request_available',energy is not None)]:check('metric '+col,mr[col]==str(expectedval))
            balance_covered=truedebt is not None and bal['lower_kwh'] is not None and bal['lower_kwh']-1e-12<=truedebt<=bal['upper_kwh']+1e-12
            wrong_balance=truedebt is not None and ((bal['status']=='within_margin' and truedebt>.01) or (bal['status']=='above_margin' and truedebt<=.01))
            check('independent balance coverage indicator',mr['balance_interval_covered']==str(bool(balance_covered)))
            check('independent wrong decisive indicator',mr['balance_wrong_decisive']==str(bool(wrong_balance)))
            same('true balance margin indicator',None if mr['balance_true_within_margin']=='' else mr['balance_true_within_margin']=='True',None if truedebt is None else truedebt<=.01)
        if (i+1)%400==0:print('verify records',i+1,flush=True)
    # Independent DP replay uses direct residual arithmetic on first-repetition
    # high-noise 10s full cases: all six mechanisms including slow ramp.
    for name in p['mechanisms']:
        i=lookup[0,name,.15,10,'full'];y=3-power[i,:360]
        for start,stop in [(0,60),(60,180),(180,360)]:
            expected,obj=independent_dp(y[start:stop],3*.15**2*math.log(stop-start),3)
            close('direct residual DP fitted values',fits[2*i+1,start:stop],expected,1e-10)
    verify_summary(metrics)
    frozen=json.loads((BASE/'source_freeze.json').read_text(encoding='utf-8'))
    for k,h in frozen['source'].items():check('scientific source frozen '+k,sha(BASE/k)==h)
    for k,h in frozen['protected'].items():check('protected history/model '+k,sha(ROOT/k)==h)
    # Basic no-oracle dependency contract.
    source=(BASE/'methods.py').read_text(encoding='utf-8')
    check('extractor has no hidden labels or simulator import',all(s not in source for s in ('hidden_native','hidden_meta','import generate','import evaluate')))
    result=dict(status='passed' if all(v['passed'] for v in CHECKS) else 'failed',checks_passed=sum(v['passed'] for v in CHECKS),checks_failed=sum(not v['passed'] for v in CHECKS),maximum_errors=MAXERR,failures=[v for v in CHECKS if not v['passed']],verifier_sha256=sha(Path(__file__)),scope='independent numerical and semantic checks; counts are software checks, not independent research samples')
    (BASE/'independent_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result));return 0 if result['status']=='passed' else 1

def verify_summary(rows):
    ev=json.loads((BASE/'evaluation.json').read_text(encoding='utf-8'))
    for s in ev['summary']:
        rr=[r for r in rows if all(str(r[k])==str(s[k]) for k in ('mechanism','observation','method')) and float(r['sigma_native_kw'])==s['sigma_native_kw'] and int(r['dt_s'])==s['dt_s']]
        check('all25 per-cell summary denominator',len(rr)==s['denominator']==25)
        for dest,field in [('stage_correct_count','stage_correct'),('power_status_correct_count','power_status_correct'),('false_onset_count','onset_false_detection'),('request_available_count','request_available'),('balance_interval_covered_count','balance_interval_covered'),('balance_wrong_decisive_count','balance_wrong_decisive')]:check('summary '+dest,s[dest]==sum(r[field]=='True' for r in rr))
        close('summary curve RMSE',s['curve_rmse_kw'],math.sqrt(math.fsum(float(r['curve_mse_kw2']) for r in rr)/25))
        for key in ('onset_s','target_s','duration_s','power_recovery_s','request_net_kwh'):
            a=s[key];err=[float(r[key+'_error']) for r in rr if r[key+'_error']!=''];eligible=sum(r['true_'+key]!='' for r in rr)
            check('summary explicit eligible and paired',a['truth_eligible']==eligible and a['paired_available']==len(err))
            same('summary conditional MAE',a['conditional_mae'],math.fsum(abs(e) for e in err)/len(err) if err else None)
            same('summary conditional bias',a['conditional_bias'],math.fsum(err)/len(err) if err else None)
            if key.endswith('_s'):check('summary unconditional timing count',a['within30_count']==sum(r[key+'_within30']=='True' for r in rr))
        for st,count in s['balance_status_counts'].items():check('summary all recovery decisions',count==sum(r['energy_balance_status']==st for r in rr))
    for s in ev['full_observation_paired']:
        rr=[r for r in rows if r['mechanism']==s['mechanism'] and r['observation']=='full' and float(r['sigma_native_kw'])==s['sigma_native_kw'] and int(r['dt_s'])==s['dt_s']]
        a=[r for r in rr if r['method']=='F0_raw_rule'];b=[r for r in rr if r['method']=='F1_segment_rule']
        check('paired full25 denominator',len(a)==len(b)==s['denominator']==25)
        for key in ('onset_s','duration_s','power_recovery_s'):
            diff=[abs(float(v[key+'_error']))-abs(float(u[key+'_error'])) for u,v in zip(a,b) if u[key+'_error']!='' and v[key+'_error']!='']
            check('paired count and improvement',s[key]['paired_count']==len(diff) and s[key]['F1_better_count']==sum(v<0 for v in diff))
            same('paired mean absolute error difference',s[key]['mean_F1_minus_F0_absolute_error'],math.fsum(diff)/len(diff) if diff else None)
            same('paired MCSE',s[key]['mcse'],float(np.std(diff,ddof=1)/math.sqrt(len(diff))) if len(diff)>1 else None)

if __name__=='__main__':raise SystemExit(main())
