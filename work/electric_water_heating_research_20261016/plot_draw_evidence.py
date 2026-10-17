"""Plot all original retained data labels; no smoothing or model prediction."""
from pathlib import Path
import csv, hashlib, json, sys
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE.parent/'python_packages/hvac_plots_20261016'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

source=BASE/'runs/DRAW_SOURCE_02/rows.csv'
summary=json.loads((BASE/'runs/DRAW_SOURCE_02/source_summary.json').read_text(encoding='utf-8'))
rows=list(csv.DictReader(source.open(encoding='utf-8',newline='')))
out=BASE/'runs/DRAW_DESCRIPTION_01';out.mkdir(exist_ok=False)
fig,axes=plt.subplots(2,3,figsize=(15,8),sharex='row',layout='constrained')
source_checks=[]
for j,s in enumerate(summary['files']):
    rr=[r for r in rows if r['file']==s['file']];x=[float(r['elapsed_s'])/60 for r in rr]
    counts={}
    for field,label,color in [('GeyserWaterThermostatTemp','Thermostat','#333333'),('InletWaterTemp','Inlet','#2271b2'),('OutletWaterTemp','Outlet','#d55e00')]:
        vals=[float(r[field]) if float(r[field])!=-127 else float('nan') for r in rr]
        axes[j,0].plot(x,vals,label=label,color=color,lw=1)
        counts[field]={'raw_rows':len(vals),'sentinel_gaps':sum(float(r[field])==-127 for r in rr)}
    axes[j,0].set_ylabel('Published temperature (°C)');axes[j,0].legend(fontsize=8)
    axes[j,1].plot(x,[float(r['WaterConsumed']) for r in rr],color='#009e73',lw=1)
    axes[j,1].set_ylabel('Water per sample (mL)')
    axes[j,2].plot(x,[float(r['PowerConsumed']) for r in rr],color='#6a3d9a',lw=1)
    axes[j,2].set_ylabel('Electric energy per sample (Wh)')
    mode='NoHeating' if 'NoHeating' in s['file'] else 'WithHeating'
    axes[j,0].set_title(f'{mode}: {s["first"][:10]}, {len(rr)} labels',loc='left',fontsize=11)
    axes[j,1].set_title(f'Published water sum: {s["interval_water_sum_including_first_mL"]/1000:.5f} L',loc='left',fontsize=10)
    axes[j,2].set_title(f'Published energy sum: {s["interval_energy_sum_including_first_Wh"]:.3f} Wh',loc='left',fontsize=10)
    for ax in axes[j]:
        ax.set_xlabel('Elapsed time from first data label (min)');ax.grid(alpha=.2)
        ax.set_xlim(min(x),max(x))
    source_checks.append({'file':s['file'],'rows':len(rr),'temperature_plot':counts,'water_points':len(rr),'energy_points':len(rr)})
fig.suptitle('Original 150 L tank discharge records: published observations, separate experiments\n'
             'Valve, desired flow and cumulative-water fields are all zero. No causal or capacity comparison.\n'
             'Temperature -127 sentinels appear as gaps; no interpolation. Timezone / interval boundaries unverified.',fontsize=12)
fig.savefig(out/'draw_observations.png',dpi=160);fig.savefig(out/'draw_observations.svg');plt.close(fig)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(out/'receipt.json').write_text(json.dumps({'status':'plotted_all_968_source_labels_no_model','source_sha256':sha(source),
    'summary_sha256':sha(BASE/'runs/DRAW_SOURCE_02/source_summary.json'),'plot_script_sha256':sha(Path(__file__)),
    'matplotlib_version':matplotlib.__version__,'plot_sources':source_checks,
    'png_visually_reviewed':False,'svg_separately_rendered':False,
    'outputs':{p.name:sha(p) for p in out.iterdir() if p.is_file()}},indent=2)+'\n',encoding='utf-8')
print(out/'draw_observations.png')
