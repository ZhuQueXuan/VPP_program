from common import *
import math,collections
out=BASE/'runs/VERIFY_CHAR_TEMPERATURE_01';out.mkdir(exist_ok=False)
run=BASE/'runs/CHAR_TEMPERATURE_01';repeat=BASE/'runs/CHAR_TEMPERATURE_02'
for n in ['observed_characteristics.json','plot_source.csv']:assert sha(run/n)==sha(repeat/n)
manifest=load(BASE/'runs/PREP_TEMPERATURE_01/summary.json')['files'];anchors=read(BASE/'runs/PREP_TEMPERATURE_01/candidates.csv');plot=read(run/'plot_source.csv');obs=load(run/'observed_characteristics.json')
assert len(plot)==len(anchors)==16751
num=0;maxdiff=0.
def close(x,y):
    global num,maxdiff
    diff=abs(x-y);assert diff<1e-9,(x,y);num+=1;maxdiff=max(maxdiff,diff)
def quantile(v,q):
    s=sorted(v);p=(len(s)-1)*q;i=math.floor(p);return s[i]+(p-i)*(s[min(i+1,len(s)-1)]-s[i])
expected={};profiles={}
for item in manifest:
    d=load(ROOT/item['path']);tr=d.get('Trace',d.get('TraceCollection'));fid=item['file_id'];rows=[r for r in anchors if r['file_id']==fid]
    values=collections.defaultdict(list)
    for r in rows:
        i=int(r['row'])-1;record={}
        for name,key in [('temperature_C','GeyserWaterThermostatTemp'),('upper_C','B0-T0'),('lower_C','B0-T8')]:
            v=tr[key][i];okay=isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=100
            record[name]=v if okay else None
            if okay:values[name].append(v)
        record['heating_flag']=tr['GeyserHeatingFlag'][i]
        if record['upper_C'] is not None and record['lower_C'] is not None:values['upper_minus_lower_C'].append(record['upper_C']-record['lower_C'])
        expected[(fid,r['block'],r['minute'])]={'row':r['row'],**record}
    profiles[fid]=values
for r,a in zip(plot,anchors):
    for key in ['file_id','split','block','minute','row']:assert r[key]==a[key]
    ref=expected[(r['file_id'],r['block'],r['minute'])]
    for key in ['temperature_C','upper_C','lower_C','heating_flag']:
        if ref[key] is None:assert r[key]==''
        else:close(float(r[key]),ref[key])
for row in obs['files']:
    fid=row['file_id'];assert row['minute_anchors']==sum(r['file_id']==fid for r in plot)
    for key,stored in row['values'].items():
        vv=profiles[fid][key];assert stored['n']==len(vv)
        for name,value in [('mean',math.fsum(vv)/len(vv)),('min',min(vv)),('median',quantile(vv,.5)),('q95',quantile(vv,.95)),('max',max(vv))]:close(stored[name],value)
pred=read(BASE/'runs/BL_TEMPERATURE_01/predictions.csv')
for r in pred:
    ref=expected[(r['file_id'],r['block'],str(int(r['minute'])+5))]
    assert r['target_row']==ref['row'];close(float(r['target_C']),ref['temperature_C'])
assert len(pred)==7331 and set(r['file_id'] for r in pred)=={'E05','E06','E07'}
for r in plot:
    if r['split']=='test':
        for key in ['temperature_C','upper_C','lower_C']:
            if r[key]!='':assert 0<=float(r[key])<=80
receipt={'status':'passed','minute_plot_rows_checked':16751,'all_target_aligned_predictions':7331,'files':7,'test_panels':3,
 'numeric_checks':num,'max_difference_C':maxdiff,'two_scientific_description_files_exact_rerun':True,
 'PNG_visually_reviewed':True,'SVG_same_figure_exported':True,'SVG_separately_rendered':False,'new_fit':0,'new_independent_prediction_points':0,
 'source_QA_receipt_sha256':sha(BASE/'runs/SOURCE_QA_02/receipt.json'),'protocol_sha256':sha(BASE/'temperature_characteristic_protocol_v1.json'),
 'verifier_sha256':sha(Path(__file__)),'scope':'Independent stdlib source-value/statistic/plot-target alignment, shares original source JSON decoder and already independently checked anchor manifest. No new physical source.'}
dump(out/'receipt.json',receipt);print(json.dumps(receipt,indent=2))
