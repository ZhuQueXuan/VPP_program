"""Describe fixed-model errors near measured power jumps; never change old score."""
from common import *
import argparse,numpy as np,pandas as pd
ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();assert Path(a.run_id).name==a.run_id
out=BASE/'runs'/a.run_id;out.mkdir(exist_ok=False)
pp=BASE/'hil_diagnostic_protocol_v1.json';assert sha(pp)==load(BASE/'hil_diagnostic_freeze_v1.json')['protocol_sha256'];p=load(pp)
cal=BASE/'runs/BL_HIL_POWER_01/calibration.json';assert sha(cal)==p['calibration_sha256'];b=load(cal)['parameters']
old=BASE/'runs/BL_HIL_POWER_01/predictions.csv';assert sha(old)==p['old_predictions_sha256']
results=[];jumps=[];testparts=[];rowflags=[]
def calculate(y,pred,mask,total):
    e=pred-y;v=e[mask]
    return {'rows':int(mask.sum()),'MAE_W':float(np.mean(abs(v))) if len(v) else None,'RMSE_W':float(np.sqrt(np.mean(v*v))) if len(v) else None,'SAE_W':float(np.sum(abs(v))),'SSE_W2':float(np.dot(v,v)),
      'row_share':float(mask.sum()/len(y)),'SAE_share':float(np.sum(abs(v))/np.sum(abs(e))),'SSE_share':float(np.dot(v,v)/np.dot(e,e))}
for name,source in sorted(p['sources'].items()):
    fp=ROOT/source['path'];assert sha(fp)==source['sha256'];d=pd.read_csv(fp);n=len(d)
    times=pd.to_datetime(d['TimeStamp']);assert np.all(np.diff(times.to_numpy())==np.timedelta64(1,'s'))
    q=d['Cooling Capacity (kW)'].to_numpy();t=d['T_Outdoor (C)'].to_numpy();outer=d['Outdoor Unit Power (W)'].to_numpy();y=outer+d['Indoor Unit Power (W)'].to_numpy()
    bc=b['B_COP'][0]+b['B_COP'][1]*q;mt=b['M_TEMP'][0]+b['M_TEMP'][1]*q+b['M_TEMP'][2]*q*(t-35.)
    idx=np.flatnonzero(abs(np.diff(outer))>=500.)+1
    difference=np.zeros(n+1,dtype=np.int64)
    for i in idx:
        lo=max(0,int(i)-60);hi=min(n,int(i)+61);difference[lo]+=1;difference[hi]-=1
        jumps.append({'file':name,'row':int(i)+1,'timestamp':str(d['TimeStamp'].iloc[i]),'delta_outer_W':float(outer[i]-outer[i-1]),'window_clipped':bool(i<60 or i+60>=n)})
    near=np.cumsum(difference[:-1])>0
    masks={'all':np.ones(n,dtype=bool),'within_60s_of_observed_jump':near,'other_rows':~near,'Q_le0_and_Ptotal_ge1000W':(q<=0)&(y>=1000)}
    split='test' if 'OAT85F_' in name or 'OAT105F_' in name else 'training_descriptive_only'
    table={'file':name,'split':split,'rows':n,'observed_jumps':len(idx),'upward':int(sum(outer[idx]-outer[idx-1]>=500.)),'downward':int(sum(outer[idx]-outer[idx-1]<=-500.)),
      'clipped_jump_windows':sum(x['window_clipped'] for x in jumps if x['file']==name),'groups':{k:{m:calculate(y,v,mask,n) for m,v in [('B_COP',bc),('M_TEMP',mt)]} for k,mask in masks.items()}}
    results.append(table)
    rowflags.extend({'file':name,'row':i+1,'near_jump':bool(v)} for i,v in enumerate(near))
    if split=='test':testparts.append((y,bc,mt,near,q))
    if 'OAT85F_' in name:
        # Old documented worst point: index672 == one-based data row673.
        context=d.iloc[492:853].copy();context.insert(0,'data_row',np.arange(493,854));context['fixed_B_COP_W']=bc[492:853];context['fixed_M_TEMP_W']=mt[492:853];context['total_electric_W']=y[492:853]
        context.to_csv(out/'worst_context.csv',index=False,float_format='%.17g')
        assert abs(mt[672]-y[672])>3908.
y,bc,mt,near,q=[np.concatenate([v[i] for v in testparts]) for i in range(5)]
masks={'all':np.ones(len(y),dtype=bool),'within_60s_of_observed_jump':near,'other_rows':~near,'Q_le0_and_Ptotal_ge1000W':(q<=0)&(y>=1000)}
pooled={k:{m:calculate(y,v,mask,len(y)) for m,v in [('B_COP',bc),('M_TEMP',mt)]} for k,mask in masks.items()}
dump(out/'summary.json',{'protocol_sha256':sha(pp),'analysis':'posthoc descriptive, no fit/no score replacement/no success gate','files':results,'pooled_old_test':pooled,'limits':p['causality'],'stage_or_command_columns_present':False})
dump(out/'jumps.json',jumps)
with (out/'row_flags.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['file','row','near_jump']);w.writeheader();w.writerows(rowflags)
dump(out/'receipt.json',{'status':'completed','script_sha256':sha(Path(__file__)),'protocol_sha256':sha(pp),'old_predictions_sha256':sha(old),'calibration_sha256':sha(cal),'outputs':{f.name:sha(f) for f in sorted(out.iterdir()) if f.is_file()}})
print(json.dumps({'files':[{k:v for k,v in f.items() if k!='groups'} for f in results],'pooled_old_test':pooled},ensure_ascii=False,indent=2))
