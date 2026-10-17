"""Post-evaluation description only. No fitting, new predictions or filters."""
from common import *
import argparse,os,sys
import numpy as np
import pandas as pd
ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args()
out=BASE/'runs'/a.run_id;out.mkdir(exist_ok=False)
frozen=load(BASE/'characteristic_protocol_v1.json')
assert sha(BASE/'curve_protocol_v1.json')==frozen['curve_protocol_sha256']
source=BASE/'runs/BL_CURVE_01';pred=pd.read_csv(source/'predictions.csv')
rows=pd.read_csv(BASE/'runs/PREP_CURVE_01/candidates.csv');rows=rows[rows.admitted].copy()
parameters=load(source/'parameters.json');observed={};plotdata={};pairs=[]
for unit in range(1,7):
    rr=rows[rows.unit==unit];test=pred[pred.unit==unit]
    item={'n':len(rr),'training_rows':int((rr.split=='training').sum()),'test_rows':len(test)}
    for key in ['wind_mps','power_kW']:
        v=rr[key].to_numpy();item[key]={'mean':float(v.mean()),'quantiles':dict(zip(['min','q25','median','q75','max'],map(float,np.quantile(v,[0,.25,.5,.75,1]))))}
    item.update({'negative_power_rows':int((rr.power_kW<0).sum()),'zero_power_rows':int((rr.power_kW==0).sum()),'positive_power_rows':int((rr.power_kW>0).sum()),'above_nominal_2050kW_rows':int((rr.power_kW>2050).sum())})
    mask=rr['row'].diff().eq(1)
    dp=rr.power_kW.diff()[mask].to_numpy();dv=rr.wind_mps.diff()[mask].to_numpy()
    item['adjacent_valid_600s_pairs']={'n':len(dp),'mean_delta_power_kW':float(dp.mean()),'min_delta_power_kW':float(dp.min()),'max_delta_power_kW':float(dp.max()),'p95_absolute_delta_power_kW':float(np.quantile(abs(dp),.95)),'p95_absolute_delta_wind_mps':float(np.quantile(abs(dv),.95)),'interpretation':'Difference between successive published10min means; not physical instantaneous ramp or commanded response.'}
    observed[str(unit)]=item
    per={}
    for split in ['training','test']:
        ss=rr[rr.split==split].copy();ss['bin_id']=np.floor(ss.wind_mps/.5).astype(int)
        table=ss.groupby('bin_id').agg(n=('wind_mps','size'),wind_mps=('wind_mps','mean'),power_kW=('power_kW','mean'))
        per[split]=[{'bin_id':int(k),'n':int(v.n),'wind_mps':float(v.wind_mps),'power_kW':float(v.power_kW)} for k,v in table.iterrows()]
    plotdata[str(unit)]=per
dump(out/'observed_characteristics.json',{'scope':frozen['scope'],'units':observed,'admitted_rows':len(rows),'all_adjacent_valid_pairs':sum(v['adjacent_valid_600s_pairs']['n'] for v in observed.values()),'quantile_method':'Linear interpolation, same as numpy quantile default. Full admitted original-year records, post-evaluation descriptive only.'})
dump(out/'power_curve_bins.json',{'bin_width_mps':0.5,'units':plotdata,'purpose':'All nonempty train/test observed bins, no rare-bin omission. Test means are descriptive, never fitted model nodes.'})
worst=load(source/'diagnostics.json')['worst_examples']['M_CURVE'];unit=worst['unit'];centre=worst['row']
context=rows[(rows.unit==unit)&(rows['row'].between(centre-3,centre+3))].copy()
context.to_csv(out/'worst_context.csv',index=False)
sys.path.insert(0,str(ROOT/'work/python_packages/hvac_plots_20261016'))
os.environ['MPLCONFIGDIR']=str(ROOT/'work/python_caches/mpl_wind_20261016')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axes=plt.subplots(2,3,figsize=(14,8.5),sharex=True,sharey=True)
for unit,ax in zip(range(1,7),axes.flat):
    rr=pred[pred.unit==unit];p=parameters['units'][str(unit)]
    ax.scatter(rr.wind_mps,rr.power_kW,s=2,color='#888888',alpha=.22,rasterized=True,edgecolors='none',label='All held-out observations')
    ax.plot(p['knot_wind_mps'],p['knot_power_kW'],color='#244e70',lw=1.7,label='Fixed training curve')
    ax.set_title(f'Kelmarsh {unit}  |  test n={len(rr):,}',fontsize=11)
    ax.axhline(2050,color='#777777',lw=.7,ls=':');ax.grid(alpha=.15);ax.set_xlim(0,27);ax.set_ylim(-100,2200)
    ax.tick_params(labelsize=9)
    if unit in [1,4]:ax.set_ylabel('Published mean active power (kW)')
    if unit>=4:ax.set_xlabel('Same-row published mean wind speed (m/s)')
fig.suptitle('Wind-power relation: six original MM92 units, mixed observed operation',fontsize=15,y=.98)
handles,labels=axes.flat[0].get_legend_handles_labels()
fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.945),ncol=2,frameon=False)
fig.text(.5,.012,'Train: Jan-Sep 2018. Held out: Oct-Dec 2018. Negative and above-nominal observations retained. Not a healthy or available-power curve.',ha='center',fontsize=10)
fig.subplots_adjust(left=.07,right=.98,bottom=.09,top=.88,hspace=.27,wspace=.15)
fig.savefig(out/'power_curves.png',dpi=170);fig.savefig(out/'power_curves.svg');plt.close(fig)
dump(out/'receipt.json',{'status':'completed_descriptive_only','new_fit':0,'new_independent_test_points':0,'new_predictions':0,
 'protocol_sha256':sha(BASE/'characteristic_protocol_v1.json'),'original_predictions_sha256':sha(source/'predictions.csv'),
 'script_sha256':sha(Path(__file__)),'matplotlib':matplotlib.__version__,
 'artifacts':{f.name:sha(f) for f in out.iterdir() if f.is_file()}})
print(json.dumps({'units':6,'admitted':len(rows),'adjacent_pairs':sum(v['adjacent_valid_600s_pairs']['n'] for v in observed.values()),'worst_context_rows':len(context),'new_fit':0},indent=2))
