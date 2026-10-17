"""Independent vector-clock/source reconstruction and explicit SVD algebra."""
from common import *
import numpy as np,pandas as pd,collections,platform
out=BASE/'runs/VERIFY_TEMPERATURE_01';out.mkdir(exist_ok=False)
pp=BASE/'temperature_protocol_v1.json';p=load(pp);assert sha(pp)==load(BASE/'temperature_freeze_v1.json')['protocol_sha256']
run=BASE/'runs/BL_TEMPERATURE_01';rep=BASE/'runs/BL_TEMPERATURE_02'
for n,h in load(run/'receipt.json')['artifacts'].items():assert sha(run/n)==h==sha(rep/n)
candidates=pd.read_csv(BASE/'runs/PREP_TEMPERATURE_01/candidates.csv');samples=pd.read_csv(BASE/'runs/PREP_TEMPERATURE_01/samples.csv')
allrebuilt=[];checks=collections.Counter();maximum=collections.defaultdict(float);triples={'training':set(),'test':set()}
def close(a,b,tol,kind):
    aa=np.asarray(a,dtype=float);bb=np.asarray(b,dtype=float);assert aa.shape==bb.shape
    assert np.array_equal(np.isnan(aa),np.isnan(bb))
    mask=np.isfinite(aa)&np.isfinite(bb);diff=float(np.max(abs(aa[mask]-bb[mask]))) if mask.any() else 0.
    assert diff<=tol,(kind,diff);checks[kind]+=aa.size;maximum[kind]=max(maximum[kind],diff)
for j,item in enumerate(p['files']):
    fid=f'E{j+1:02d}';f=ROOT/item['path'];assert sha(f)==item['sha256'];d=load(f);tr=d.get('Trace',d.get('TraceCollection'));tk='TimeStamp' if 'TimeStamp' in tr else 'Timestamp';n=len(tr[tk])
    df=pd.DataFrame(tr);s=df[tk].astype('str');tt=pd.Series(pd.NaT,index=df.index,dtype='datetime64[ns]')
    for fmt in ['%Y-%m-%dT%H:%M:%S','%d/%m/%Y %H:%M','%Y/%m/%d %H:%M','%I:%M:%S %p','%H:%M:%S']:
        parsed=pd.to_datetime(s,format=fmt,errors='coerce');tt=tt.fillna(parsed)
    bad=tt.isna();back=(tt<tt.shift())&tt.notna()&tt.shift().notna();blocks=(bad|back).cumsum()
    df['block']=blocks;df['minute']=np.floor((tt-pd.Timestamp('1900-01-01')).dt.total_seconds()/60);df['row']=np.arange(1,n+1)
    aa=df[~bad].groupby(['block','minute'],sort=False).tail(1).copy();index=pd.MultiIndex.from_frame(aa[['block','minute']]);indexed=aa.set_index(['block','minute'])
    for key in ['GeyserWaterThermostatTemp','GeyserHeatingFlag','ChamberTemp1','ChamberTemp2','B0-T0','B0-T8']:indexed[key]=pd.to_numeric(indexed[key],errors='coerce')
    def shifted(k,column):
        ix=pd.MultiIndex.from_arrays([aa.block.to_numpy(),aa.minute.to_numpy()+k]);return indexed[column].reindex(ix).to_numpy()
    full=np.ones(len(aa),bool)
    for k in range(-5,6):full&=index.get_indexer(pd.MultiIndex.from_arrays([aa.block,aa.minute+k]))>=0
    cur=shifted(0,'GeyserWaterThermostatTemp');prev=shifted(-5,'GeyserWaterThermostatTemp');target=shifted(5,'GeyserWaterThermostatTemp')
    c1=shifted(0,'ChamberTemp1');c2=shifted(0,'ChamberTemp2');top=shifted(0,'B0-T0');bottom=shifted(0,'B0-T8');flag=shifted(0,'GeyserHeatingFlag')
    vals=np.column_stack([cur,prev,target,c1,c2,top,bottom]);invalid=(~np.isfinite(vals)|(vals<0)|(vals>100)).any(axis=1)&full
    badflag=(~np.isin(flag,[0,1]))&full;ok=full&~invalid&~badflag
    cc=candidates[candidates.file_id==fid];assert len(cc)==len(aa)
    for key,value in [('block',aa.block),('minute',aa.minute),('row',aa.row),('clock_window_incomplete',~full),('temperature_invalid',invalid),('heating_flag_invalid',badflag),('admitted',ok)]:assert np.array_equal(cc[key],value),(fid,key);checks['anchor_keys_flags']+=len(aa)
    split='test' if item['name'].startswith(('Exp2_6','Exp2_9')) else 'training'
    rebuilt=pd.DataFrame({'file_id':fid,'split':split,'block':aa.block.to_numpy(),'minute':aa.minute.to_numpy(),'row':aa.row.to_numpy(),
      'previous_row':shifted(-5,'row'),'target_row':shifted(5,'row'),'temperature_C':cur,'previous_temperature_C':prev,'heating_flag':flag,'ambient_C':(c1+c2)/2,'top_C':top,'bottom_C':bottom,'target_C':target})[ok]
    allrebuilt.append(rebuilt)
    # Exact three-source-row payload overlap diagnostic; no source sorting or deduplication.
    keys=sorted(k for k in tr if k!=tk);recent=[]
    for i in range(n):
        if bad.iloc[i]:recent=[];continue
        h=hashlib.sha256(repr(tuple(tr[k][i] for k in keys)).encode()).digest();recent.append(h)
        if len(recent)>3:recent.pop(0)
        if len(recent)==3:triples[split].add(hashlib.sha256(b''.join(recent)).hexdigest())
rr=pd.concat(allrebuilt,ignore_index=True);assert len(rr)==len(samples)==16636
for key in ['file_id','split','block','minute','row','previous_row','target_row']:assert np.array_equal(rr[key],samples[key]),key
for key in ['temperature_C','previous_temperature_C','heating_flag','ambient_C','top_C','bottom_C','target_C']:close(rr[key],samples[key],1e-10,'sample_'+key)
train=rr[rr.split=='training'];test=rr[rr.split=='test'];cnt=train.file_id.value_counts();w=np.array([1/np.sqrt(cnt[x]) for x in train.file_id])
def xof(df):
    t=df.temperature_C.to_numpy();return np.column_stack([np.ones(len(df)),t-df.previous_temperature_C.to_numpy(),df.heating_flag.to_numpy(),df.ambient_C.to_numpy()-t,df.top_C.to_numpy()-t,df.bottom_C.to_numpy()-t])
x=xof(train);dy=(train.target_C-train.temperature_C).to_numpy();u,s,vh=np.linalg.svd(x*w[:,None],full_matrices=False);assert (s>s[0]*1e-12).sum()==6
beta=vh.T@((u.T@(dy*w))/s);param=load(run/'parameters.json');close(beta,param['beta'],1e-9,'coefficients');close(x.min(axis=0),param['feature_min'],1e-9,'feature_range');close(x.max(axis=0),param['feature_max'],1e-9,'feature_range')
pred=pd.read_csv(run/'predictions.csv');xx=xof(test)
for key,value in [('B_P',test.temperature_C),('B_TREND',2*test.temperature_C-test.previous_temperature_C),('M_LAYER6',test.temperature_C.to_numpy()+xx@beta)]:close(pred[key],value,1e-8,'prediction_'+key)
outside=((xx<x.min(axis=0))|(xx>x.max(axis=0))).any(axis=1);assert np.array_equal(outside,pred.outside_training_range)
groups={'overall':np.ones(len(pred),bool),**{fid:(pred.file_id==fid).to_numpy() for fid in sorted(pred.file_id.unique())},
 'heating_flag1':pred.heating_flag==1,'heating_flag0':pred.heating_flag==0,'outside_training_range':outside,'inside_training_range':~outside}
metrics=load(run/'metrics.json');ind={}
for g,mask in groups.items():
    sel=pred[mask];assert metrics[g]['n']==len(sel);ind[g]={}
    for model in ['B_P','B_TREND','M_LAYER6']:
        err=sel[model].to_numpy()-sel.target_C.to_numpy();mm={'mae_C':float(np.mean(abs(err))),'rmse_C':float(np.sqrt(np.mean(err**2))),'bias_C':float(err.mean()),'max_abs_C':float(np.max(abs(err)))} if len(sel) else {k:None for k in ['mae_C','rmse_C','bias_C','max_abs_C']}
        for k,value in mm.items():
            if value is None:assert metrics[g]['models'][model][k] is None
            else:close([value],[metrics[g]['models'][model][k]],1e-8,'metrics_C')
        ind[g][model]=mm
gate={g:all(ind[g]['M_LAYER6'][k]<ind[g][m][k] for m in ['B_P','B_TREND'] for k in ['mae_C','rmse_C']) for g in ['overall']+sorted(pred.file_id.unique())+['heating_flag1']}
diag=load(run/'diagnostics.json');assert gate==diag['gate_checks'] and all(gate.values())==diag['gate_passed']
for model,row in diag['worst_examples'].items():
    worst=pred.loc[(pred[model]-pred.target_C).abs().idxmax()];assert (worst.file_id,int(worst.row))==(row['file_id'],int(row['row']))
intersection=triples['training']&triples['test']
dump(out/'receipt.json',{'status':'passed','source_rows':130438,'minute_candidates':16751,'admitted':len(rr),'training_rows':len(train),'test_rows':len(test),
 'checks':dict(checks),'max_difference':dict(maximum),'identical_three_raw_row_payloads_across_train_test':len(intersection),
 'overlap_check_scope':'Exact allsignal three-row payloads ignoring timestamp; no match does not prove independent physical events. All datedAug18overlaps are together in heldout.',
 'protocol_sha256':sha(pp),'admission_sha256':sha(BASE/'runs/PREP_TEMPERATURE_01/admission.json'),'run_receipt_sha256':sha(run/'receipt.json'),
 'repeat_receipt_sha256':sha(rep/'receipt.json'),'verifier_sha256':sha(Path(__file__)),'five_scientific_files_exact_rerun':True,
 'scope':'Independent vector clock/anchor/sample construction and explicit SVD, sameJSONdecoder/source. No new physical experiment or online timing validation.'})
print(json.dumps(load(out/'receipt.json'),indent=2))
