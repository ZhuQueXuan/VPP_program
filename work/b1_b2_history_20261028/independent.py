"""Read-only independent arithmetic audits; never writes old receipts."""
import json
import numpy as np
import joblib
from scipy.special import softmax
from io_utils import BASE,RAW,ROOT,read,write,sha
from api import predict_with_history

def main():
    raw=np.load(RAW/'observations.npz');ff=np.load(BASE/'b1_features.npz')['features'];models=joblib.load(BASE/'models.joblib');selection=read(BASE/'selection.json');result=read(BASE/'results.json');checks=0;maxprob=0.;maxenergy=0.
    temp=np.zeros((6,30));temp[1]=1;temp[2,2:]=1;temp[3,5:]=1;temp[4,:15]=1;temp[5]=.7;fractions=temp.mean(axis=1)
    for r in range(20):
        power=raw['power'][r];b=raw['b'][r];T=raw['T'][r];q=raw['q'][r];ref=b[:,:,None]*(np.arange(120)<T[:,:,None]);red=ref[None]-power;y=raw['label'][r]
        assert power.min()>-1e-8 and power.max()<7.2+1e-8;err=float(abs(power.sum(axis=-1)/60-raw['E'][r][None]).max());maxenergy=max(maxenergy,err);assert err<1e-9;checks+=power.size+power.shape[0]*400*12
        assert np.allclose(red[:,:,:,:30]/q[None,:,:,None],temp[y],atol=1e-12,rtol=0);assert np.array_equal(raw['A'][r]==-1,np.broadcast_to(~raw['eligible'][r],(3,400,12)));checks+=28800
        norm=red[:,:,:,:30]/q[None,:,:,None];a=norm.mean(axis=-1);on=red[:,:,:,:30]>=.15;target=norm>=.9
        onset=np.where(on.any(axis=-1),on.argmax(axis=-1)/30,1.);targetdelay=np.where(target.any(axis=-1),target.argmax(axis=-1)/30,1.)
        independent=np.stack([a,onset,targetdelay,target.any(axis=-1)],axis=-1);assert np.allclose(ff[r],independent,atol=1e-12,rtol=0);checks+=ff[r].size
        d=np.load(BASE/f'replicate_{r:02d}.npz');u=d['user'];j=d['event'];s=d['scene'];sp=d['split'];assert np.array_equal(raw['split'][r,u],sp)
        for split,targets in enumerate([[3,4,5,6],[7,8],[9,10,11]]):assert set(j[sp==split])==set(targets)
        assert not (set(u[sp==0])&set(u[sp==1]) or set(u[sp==0])&set(u[sp==2]) or set(u[sp==1])&set(u[sp==2]));checks+=4
        S=[];H=[]
        for scene,user,event in zip(s,u,j):
            f=independent[scene,user,event-3:event];S.append([f[:,0].mean(),f[-1,0],f[:,1].mean(),f[:,2].mean(),f[:,3].mean(),(f[-1,0]-f[0,0])/2]);H.append(norm[scene,user,event-3:event].ravel())
            assert (event-1)*180+120<=event*180;checks+=1
        assert np.allclose(S,d['S'],atol=1e-12) and np.allclose(H,d['H'],atol=1e-12);checks+=d['S'].size+d['H'].size
        m=models[r];train=sp==0;assert np.allclose(m['scale'].mean_,d['H'][train].mean(axis=0),atol=1e-12);checks+=90
        z=(d['H']-m['scale'].mean_)/m['scale'].scale_;pca=(z-m['pca'].mean_)@m['pca'].components_.T;ae=z.copy()
        for layer in range(2):ae=np.tanh(ae@m['ae'].coefs_[layer]+m['ae'].intercepts_[layer])
        designs=[d['X'],np.c_[d['X'],d['S']],np.c_[d['X'],pca],np.c_[d['X'],ae]];pred=[]
        for method,v in enumerate(designs):
            h=m['heads'][method];v=(v-h[0].mean_)/h[0].scale_;p=softmax(v@h[1].coef_.T+h[1].intercept_,axis=1);p[~d['eligible']]=[1,0,0,0,0,0];err=float(abs(p-d['probabilities'][method]).max());maxprob=max(maxprob,err);assert err<1e-11;pred.append(p);checks+=p.size
        def score(p,mask):
            e=d['q'][mask]*(p[mask,1:]@fractions[1:]);a=d['q'][mask]*fractions[d['y'][mask]];sv=np.isin(d['y'][mask],[1,2]);return dict(mse=float(np.mean((e-a)**2)),rmse=float(np.sqrt(np.mean((e-a)**2))),mae=float(np.mean(abs(e-a))),brier=float(np.mean((p[mask,1:3].sum(axis=1)-sv)**2)))
        scores=[score(p,sp==1) for p in pred];candidates=[i for i in range(1,4) if scores[i]['mse']<scores[0]['mse'] and scores[i]['brier']<=scores[0]['brier']];chosen=min(candidates,key=lambda i:(scores[i]['mse'],i)) if candidates else 0;assert chosen==selection['selected'][r];checks+=1
        for name,p in zip(['C0','C1','C2','C3','selected','frozen_B2'],pred+[pred[chosen],d['base']]):
            for group in ['all','no_persistence','stable_user_effect','drifting_user_effect','eligible']:
                mask=sp==2
                if group=='eligible':mask&=d['eligible']
                elif group!='all':mask&=s==['no_persistence','stable_user_effect','drifting_user_effect'].index(group)
                score0=score(p,mask);row=next(x for x in result['records'] if x['rep']==r and x['method']==name and x['group']==group)
                assert all(abs(row[k]-v)<1e-11 for k,v in score0.items());checks+=4
        print('independent replicate',r+1,flush=True)
    # API parity uses public records rather than hidden generator states.
    case=read(BASE/'example_input.json');api=predict_with_history(case);assert api['status']=='ok';p=np.array(api['six_outcome_probabilities']);path=case['current']['q']*(p[1:]@temp[1:]);assert abs(path.mean()-api['expected_delivery_kw'])<1e-12;assert abs(p[1:3].sum()-api['service30_v1_probability'])<1e-12;checks+=3
    import copy
    cold=copy.deepcopy(case);cold['history']=[];r=predict_with_history(cold);assert r['cold_start'] and r['history_method']=='C0';checks+=1
    for permission,status in [(False,'blocked'),(0,'blocked'),('0','unavailable'),('1','unavailable')]:
        v=copy.deepcopy(case);v['current']['permission']=permission;r=predict_with_history(v);assert r['status']==status and r['committed_kw'] is None;checks+=1
    v=copy.deepcopy(case);v['history'][0]['resource_id']='other';assert predict_with_history(v)['status']=='unavailable';checks+=1
    v=copy.deepcopy(case);v['history'][2]['available_at']='2026-10-28T10:00:00+08:00';assert predict_with_history(v)['status']=='unavailable';checks+=1
    for fn in ['source_freeze.json','prediction_freeze.json']:
        f=read(BASE/fn)
        if fn=='source_freeze.json':
            for group,root in [('source',BASE),('protected',ROOT)]:
                for n,h in f[group].items():assert sha(root/n)==h,n;checks+=1
        else:
            for n,h in f.items():assert sha(BASE/n)==h,n;checks+=1
    write(BASE/'example_output.json',api)
    write(BASE/'independent_checks.json',dict(status='passed',checks=checks,max_prediction_abs_difference=maxprob,max_energy_error_kwh=maxenergy,raw_sha=sha(RAW/'observations.npz'),old_files_unchanged=len(read(BASE/'source_freeze.json')['protected']),limits='Synthetic exact-meter finite family only. No real-data validation.'))
    print('independent passed',checks,flush=True)

if __name__=='__main__':main()
