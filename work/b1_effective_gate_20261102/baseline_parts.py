import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.special import expit
from b1_algorithm.process import _known_duration as KD,_local_response as LR

def true_durations(clean,starts,step):return KD.durations(clean,starts,step)

def adopted(cases,curves,return_masks=False):
    X=np.vstack([KD.input_features(c,curves[c['task_id']]['cpop']['prediction'],curves[c['task_id']]['duration_fusion']['prediction']) for c in cases]);meta,models,_=KD._artifacts();cfg=meta['configuration'];p=expit(LR.fast_predict(models['event.json'],X));delta=np.column_stack([LR.fast_predict(models[n],X) for n in ['cumulative.json','longest.json']]);out=[]
    for i,c in enumerate(cases):
        f=curves[c['task_id']];v=KD.refine(c,f['cpop']['prediction'],f['duration_fusion']['prediction'],delta[i],p[i]>=cfg['event_threshold'],cfg['shrink'])
        out.append(v)
    out=np.asarray(out);masks=[];pending=[];xx=[];slices=[];offset=0
    for i,c in enumerate(cases):
        s=np.asarray(c['starts_s']);task=(s>=0)&(s<1800);y=np.asarray(c['reference_kw'])-np.asarray(c['power_kw'])
        mask=(np.asarray(curves[c['task_id']]['duration_fusion']['prediction'])>=.15)&task
        if out[i,0]<=0:mask[:]=False
        masks.append(mask)
        if out[i,0]<=0 and p[i]>=.025 and abs(np.median(y[task]))<=.075:
            x=LR.raw_features(c);pending.append(i);xx.append(x);slices.append((offset,offset+len(x)));offset+=len(x)
    if pending:
        mm,tree=LR._artifacts();prob=expit(LR.fast_predict(tree,np.vstack(xx)));cc=mm['configuration']
        for i,(a,b) in zip(pending,slices):
            c=cases[i];masks[i],out[i],_=LR.rescue(c,curves[c['task_id']]['duration_fusion']['prediction'],out[i],p[i],prob[a:b],cc['threshold'],cc['z_threshold'],cc['amplitude_margin_sigma'])
    return (out,X,masks) if return_masks else (out,X)

def eligible(case,baseline):
    if baseline[0]<=0:return False
    s=np.asarray(case['starts_s']);task=(s>=0)&(s<1800);y=np.asarray(case['reference_kw'])-np.asarray(case['power_kw']);median=float(np.median(y[task]))
    return not (median>.4 or (baseline[0]<=60.+1e-8 and abs(median)<=.075))

def gap_features(case,cpop,support,baseline):
    s=np.asarray(case['starts_s']);task=(s>=0)&(s<1800);step=case['ends_s'][0]-s[0];y=np.asarray(case['reference_kw'])-np.asarray(case['power_kw']);out=[];n=int(task.sum())
    traces=[y,np.asarray(cpop),np.asarray(support)]
    traces += [uniform_filter1d(y,max(1,int(round(seconds/step))),mode='nearest') for seconds in [30.,60.,120.]]
    for raw in traces:
        z=raw[task]
        for level in [.10,.15,.20]:
            mask=z>=level;edge=np.diff(np.r_[False,mask,False].astype(int));a=np.flatnonzero(edge==1);b=np.flatnonzero(edge==-1);length=b-a;order=np.argsort(-length)
            out.extend([float(mask.sum()/n),len(a)/n])
            for k in range(3):
                if k<len(order):j=order[k];out.extend([length[j]/n,a[j]/n,b[j]/n])
                else:out.extend([0.,0.,0.])
            if len(a)>1:
                gaps=a[1:]-b[:-1];out.extend([float(gaps.sum()/n),float(gaps.max()/n),float(len(gaps)/n)])
            else:out.extend([0.,0.,0.])
    out.extend(np.asarray(baseline)/1800.);out.append(baseline[1]/max(baseline[0],step))
    return np.asarray(out,np.float32)

def features(case,cpop,support,baseline,old_features=None):
    x=KD.input_features(case,cpop,support) if old_features is None else old_features
    return np.r_[x,gap_features(case,cpop,support,baseline)].astype(np.float32)

def refine(case,baseline,prediction,mix,head):
    old=np.asarray(baseline,float);s=np.asarray(case['starts_s']);task=(s>=0)&(s<1800);step=case['ends_s'][0]-s[0];y=np.asarray(case['reference_kw'])-np.asarray(case['power_kw']);median=float(np.median(y[task]))
    if old[0]<=0 or median>.4 or (old[0]<=60.+1e-8 and abs(median)<=.075):return old.copy()
    proposed_c=float(prediction[0])*1800.
    proposed_l=float(prediction[1])*proposed_c if head=='fraction' else float(prediction[1])*1800.
    value=np.rint(((1-mix)*old+mix*np.array([proposed_c,proposed_l]))/step)*step
    value[0]=np.clip(value[0],step,1800.);value[1]=np.clip(value[1],0.,value[0])
    if 0<value[1]<30.:value[1]=0.
    if step>=30. and value[0]>0:value[1]=max(step,value[1])
    count=int(round(value[0]/step));minimum=int(np.ceil(count/(int(task.sum())-count+1)))
    if minimum*step>=30.-1e-8:value[1]=max(value[1],minimum*step)
    return value
