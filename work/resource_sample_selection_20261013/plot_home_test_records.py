"""Plot all frozen native records; never connect lines across missing time."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'teacher_storage_brief_20261014/plot_dependencies'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import dates as mdates,font_manager
import pandas as pd
pa=argparse.ArgumentParser();pa.add_argument('--audit-run',required=True);a=pa.parse_args()
if not a.audit_run.isidentifier():raise ValueError('simple run ID required')
folder=ROOT/'downloads/rwth_home_test_record_diagnostic_20261014'/a.audit_run
out=folder/'test_near_native_curves.png';receipt=folder/'figure_receipt.json'
if out.exists() or receipt.exists():raise FileExistsError('choose another audit folder')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
f=pd.read_csv(folder/'raw_window_and_derived.csv');f['native_time']=pd.to_datetime(f['native_time'])
s=json.loads((folder/'summary.json').read_text('utf-8'))
p=json.loads((ROOT/'home_test_record_diagnostic_protocol_v1.json').read_text('utf-8'))
font_manager.fontManager.addfont('C:/Windows/Fonts/msyh.ttc')
plt.rcParams.update({'font.family':font_manager.FontProperties(fname='C:/Windows/Fonts/msyh.ttc').get_name(),'axes.unicode_minus':False,'font.size':10})
fig,axes=plt.subplots(3,1,figsize=(12,8.2),sharex=True,layout='constrained')
fig.suptitle('系统01 / 2019-07-01：受控测试附近的原生记录',fontsize=15)
for bid,x in f.groupby('block_id',sort=False):
    kw={'label':'原始电压' if bid==0 else None,'lw':.8,'color':'#235789'}
    axes[0].plot(x['native_time'],x['V_in_V'],**kw)
    axes[1].plot(x['native_time'],x['I_in_A'],lw=.8,color='#168575')
    axes[2].plot(x['native_time'],x['P_in_W']/1000,lw=.8,color='#b8474d',label='发布P列' if bid==0 else None)
    axes[2].plot(x['native_time'],x['UI_reconstructed_W']/1000,lw=.6,alpha=.7,color='#235789',label='U×I' if bid==0 else None)
    interp=x.loc[x['Interpolated'].eq(1)]
    axes[0].scatter(interp['native_time'],interp['V_in_V'],s=4,color='#dd8c1b',zorder=5,label='出版方插值' if len(interp) else None)
for ax in axes:
    for g in s['gaps']:
        ax.axvspan(pd.Timestamp(g['start']),pd.Timestamp(g['end_exclusive']),color='#b3b3b3',alpha=.25)
    ax.axvline(pd.Timestamp(p['test_start_native']),color='#a16b12',ls='--',lw=1)
    ax.set_xlim(pd.Timestamp(p['window_start_inclusive']),pd.Timestamp(p['window_end_exclusive']))
    ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
axes[0].set_ylabel('电压 / V');axes[0].legend(loc='lower right',fontsize=9)
axes[0].text(pd.Timestamp(p['test_start_native']),166.5,'作者索引起点 13:55:06',ha='center',fontsize=9)
axes[1].set_ylabel('端口电流 / A\n充电为正');axes[1].axhline(0,color='#999999',lw=.5)
axes[2].set_ylabel('功率 / kW\n充电为正');axes[2].legend(loc='lower right',fontsize=9)
axes[2].xaxis.set_major_locator(mdates.HourLocator(interval=3));axes[2].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
axes[2].set_xlabel('原生时间；灰色为缺口，曲线不跨缺口连接；索引起点不代表已知测试结束/满空边界')
fig.savefig(out,dpi=150,facecolor='white');plt.close(fig)
receipt.open('x',encoding='utf-8').write(json.dumps({'path':out.name,'sha256':sha(out),'source_sha256':sha(folder/'raw_window_and_derived.csv'),'code_sha256':sha(Path(__file__)),
    'plot':'all 48118 original rows, no resampling, block lines separate, published interpolation flagged, no inferred test endpoint'},ensure_ascii=False,indent=2))
print(str(out.resolve()))
