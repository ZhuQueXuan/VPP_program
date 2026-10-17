"""Independent stdlib/ordered-quantile description checks; no refitting."""
from common import *
import math,collections
out=BASE/'runs/VERIFY_CHAR_CURVE_01';out.mkdir(exist_ok=False)
run=BASE/'runs/CHAR_CURVE_01';repeat=BASE/'runs/CHAR_CURVE_02'
for n in ['observed_characteristics.json','power_curve_bins.json','worst_context.csv']:assert sha(run/n)==sha(repeat/n)
raw=[r for r in read(BASE/'runs/PREP_CURVE_01/candidates.csv') if r['admitted']=='True']
obs=load(run/'observed_characteristics.json');bins=load(run/'power_curve_bins.json');num=0;maximum=0.
def check(x,y,tol=1e-8):
    global num,maximum
    d=abs(x-y);assert d<=tol,(x,y,d);num+=1;maximum=max(maximum,d)
def quantile(values,q):
    ss=sorted(values);pos=(len(ss)-1)*q;j=math.floor(pos);w=pos-j
    return ss[j]+w*(ss[min(j+1,len(ss)-1)]-ss[j])
pairtotal=0
for unit in range(1,7):
    rr=[r for r in raw if int(r['unit'])==unit];dd=obs['units'][str(unit)]
    assert dd['n']==len(rr) and dd['training_rows']==sum(r['split']=='training' for r in rr)
    assert dd['test_rows']==sum(r['split']=='test' for r in rr)
    for key in ['wind_mps','power_kW']:
        values=[float(r[key]) for r in rr];check(dd[key]['mean'],math.fsum(values)/len(values))
        for name,q in zip(['min','q25','median','q75','max'],[0,.25,.5,.75,1]):check(dd[key]['quantiles'][name],quantile(values,q))
    ps=[float(r['power_kW']) for r in rr]
    for name,count in [('negative_power_rows',sum(v<0 for v in ps)),('zero_power_rows',sum(v==0 for v in ps)),('positive_power_rows',sum(v>0 for v in ps)),('above_nominal_2050kW_rows',sum(v>2050 for v in ps))]:assert dd[name]==count
    dp=[];dv=[]
    for previous,current in zip(rr,rr[1:]):
        if int(current['row'])-int(previous['row'])==1:
            dp.append(float(current['power_kW'])-float(previous['power_kW']));dv.append(float(current['wind_mps'])-float(previous['wind_mps']))
    item=dd['adjacent_valid_600s_pairs'];assert item['n']==len(dp);pairtotal+=len(dp)
    for key,value in [('mean_delta_power_kW',math.fsum(dp)/len(dp)),('min_delta_power_kW',min(dp)),('max_delta_power_kW',max(dp)),('p95_absolute_delta_power_kW',quantile([abs(v) for v in dp],.95)),('p95_absolute_delta_wind_mps',quantile([abs(v) for v in dv],.95))]:check(item[key],value)
    for split in ['training','test']:
        groups=collections.defaultdict(list)
        for r in rr:
            if r['split']==split:groups[math.floor(float(r['wind_mps'])/.5)].append(r)
        stored=bins['units'][str(unit)][split];assert [r['bin_id'] for r in stored]==sorted(groups)
        for r in stored:
            ss=groups[r['bin_id']];assert r['n']==len(ss)
            for key in ['wind_mps','power_kW']:check(r[key],math.fsum(float(v[key]) for v in ss)/len(ss))
        if split=='training':
            params=load(BASE/'runs/BL_CURVE_01/parameters.json')['units'][str(unit)]
            assert params['bin_ids']==[r['bin_id'] for r in stored]
            for row,x,y in zip(stored,params['knot_wind_mps'],params['knot_power_kW']):check(row['wind_mps'],x);check(row['power_kW'],y)
assert pairtotal==obs['all_adjacent_valid_pairs']==303865 and len(raw)==obs['admitted_rows']==303987
worst=load(BASE/'runs/BL_CURVE_01/diagnostics.json')['worst_examples']['M_CURVE']
expected=[r for r in raw if int(r['unit'])==worst['unit'] and abs(int(r['row'])-worst['row'])<=3]
context=read(run/'worst_context.csv');assert len(context)==len(expected)==7
for a,b in zip(context,expected):
    for key in b:
        if key in ['wind_mps','power_kW']:check(float(a[key]),float(b[key]))
        else:assert a[key]==b[key],(key,a[key],b[key])
pred=read(BASE/'runs/BL_CURVE_01/predictions.csv');assert len(pred)==69236
for r in pred:assert 0<=float(r['wind_mps'])<=27 and -100<=float(r['power_kW'])<=2200
assert set(int(r['unit']) for r in pred)==set(range(1,7))
current=ROOT/'resource_research_results/wind_power';release=load(current/'results/release_validation.json')
for n in ['code/wind_curve.py','parameters/kelmarsh_mixed_curve_v1.json']:
    assert sha(current/n)==release['verified_files'][n]
value={'status':'passed','scope':'Independent stdlib description and ordered quantiles versus pandas/NumPy. Original admitted source rows already independently verified by VERIFY_CURVE_01. No new physical source or blind prediction.',
 'admitted_rows':len(raw),'all_adjacent_pairs_checked':pairtotal,'plot_source_test_rows_checked':len(pred),
 'units':6,'worst_context_rows':7,'numeric_checks':num,'max_difference':maximum,
 'three_scientific_artifacts_exact_replay':True,'PNG_visually_reviewed':True,'SVG_separately_rendered':False,
 'SVG_same_figure_exported':True,'new_fit':0,'new_prediction_points':0,
 'protocol_sha256':sha(BASE/'characteristic_protocol_v1.json'),'description_receipt_sha256':sha(run/'receipt.json'),
 'verifier_sha256':sha(Path(__file__))}
dump(out/'receipt.json',value);print(json.dumps(value,indent=2))
