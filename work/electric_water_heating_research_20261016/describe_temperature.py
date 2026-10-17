"""Post-score descriptive all-file evidence; no new fits or forecasts."""
from common import *
import argparse,math,sys,os
import numpy as np
import pandas as pd
ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();out=BASE/'runs'/a.run_id;out.mkdir(exist_ok=False)
protocol=load(BASE/'temperature_characteristic_protocol_v1.json');pre=BASE/'runs/PREP_TEMPERATURE_01';manifest=load(pre/'summary.json')['files'];anchors=read(pre/'candidates.csv')
summary=[];plotrows=[]
for item in manifest:
    d=load(ROOT/item['path']);tr=d.get('Trace',d.get('TraceCollection'));rr=[r for r in anchors if r['file_id']==item['file_id']]
    vals={k:[] for k in ['temperature_C','upper_C','lower_C','upper_minus_lower_C']}
    for r in rr:
        i=int(r['row'])-1;raw=[tr[k][i] for k in ['GeyserWaterThermostatTemp','B0-T0','B0-T8']]
        ok=[isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=100 for v in raw]
        for name,value,flag in zip(['temperature_C','upper_C','lower_C'],raw,ok):
            if flag:vals[name].append(value)
        if ok[1] and ok[2]:vals['upper_minus_lower_C'].append(raw[1]-raw[2])
        plotrows.append({'file_id':item['file_id'],'split':item['split'],'block':int(r['block']),'minute':int(r['minute']),'row':i+1,
          'temperature_C':raw[0] if ok[0] else None,'upper_C':raw[1] if ok[1] else None,'lower_C':raw[2] if ok[2] else None,'heating_flag':tr['GeyserHeatingFlag'][i]})
    ss={}
    for name,v in vals.items():ss[name]={'n':len(v),'mean':float(np.mean(v)),'min':float(min(v)),'median':float(np.median(v)),'q95':float(np.quantile(v,.95)),'max':float(max(v))}
    summary.append({'file_id':item['file_id'],'name':item['name'],'split':item['split'],'minute_anchors':len(rr),'values':ss})
dump(out/'observed_characteristics.json',{'scope':protocol['scope'],'files':summary,'total_minute_anchors':len(anchors),'temperature_profile':'Original B0-T0 upper andB0-T8 lower only,not volume-weightedmean or tankenergy. All source-temperature-invalid points omitted only from their own descriptive statistic/left gap on plot.'})
with (out/'plot_source.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(plotrows[0]));w.writeheader();w.writerows(plotrows)
sys.path.insert(0,str(ROOT/'work/python_packages/hvac_plots_20261016'))
os.environ['MPLCONFIGDIR']=str(ROOT/'work/python_caches/mpl_water_20261016')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plot=pd.DataFrame(plotrows);pred=pd.read_csv(BASE/'runs/BL_TEMPERATURE_01/predictions.csv')
fig,axes=plt.subplots(3,1,figsize=(13,9.5));testfiles=[r for r in manifest if r['split']=='test']
for ax,item in zip(axes,testfiles):
    rr=plot[plot.file_id==item['file_id']];pp=pred[pred.file_id==item['file_id']];start=rr.minute.min()
    ax.fill_between((rr.minute-start)/60,rr.lower_C,rr.upper_C,color='#bdbdbd',alpha=.25,label='Observed lower-to-upper sensor span')
    ax.plot((rr.minute-start)/60,rr.temperature_C,color='#4b4b4b',lw=.85,label='Published thermostat observations')
    ax.plot((pp.minute+5-start)/60,pp.M_LAYER6,color='#244e70',lw=.8,alpha=.9,label='Fixed predictor (aligned to target label)')
    ax.set_title(f"{item['file_id']} | {item['name'].replace('.json','')} | held-out n={len(pp):,}",fontsize=10)
    ax.set_ylabel('Temperature (C)');ax.set_xlabel('Published clock-label hours from first observed minute')
    ax.grid(alpha=.16);ax.tick_params(labelsize=9);ax.set_ylim(0,80)
handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,ncol=3,loc='upper center',bbox_to_anchor=(.5,.949),frameon=False,fontsize=9)
fig.suptitle('Electric storage water heater: all three held-out experiment files',fontsize=15,y=.984)
fig.text(.5,.012,'One 150 L horizontal resistive tank. Input current-minute availability is assumed. Clock labels do not establish exact physical300s lead time.',ha='center',fontsize=9)
fig.subplots_adjust(left=.07,right=.985,bottom=.075,top=.895,hspace=.51)
fig.savefig(out/'test_temperature_curves.png',dpi=170);fig.savefig(out/'test_temperature_curves.svg');plt.close(fig)
dump(out/'receipt.json',{'status':'completed_post_score_description','new_fit':0,'new_prediction_points':0,
 'protocol_sha256':sha(BASE/'temperature_characteristic_protocol_v1.json'),'script_sha256':sha(Path(__file__)),
 'artifacts':{f.name:sha(f) for f in out.iterdir() if f.is_file()}})
print(json.dumps({'all_minute_anchors':len(anchors),'all_test_prediction_points':len(pred),'files':len(manifest),'panels':3}))
