"""Show native raw failed-block curves; no resampling or model change."""
from pathlib import Path
import os,sys,json,hashlib
ROOT=Path(__file__).resolve().parent
FOLDER=ROOT/'downloads/rwth_home_local_span_20261014/failure_diagnostics/QA_HOME_FAILURE_20261014_01'
OUT=FOLDER/'failed_span_curves.png'
if OUT.exists():raise FileExistsError(OUT)
os.environ['MPLCONFIGDIR']=str(FOLDER/'mpl_cache')
sys.path.insert(0,str(ROOT.parent/'teacher_storage_brief_20261014/plot_dependencies'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import dates as mdates,font_manager
import pandas as pd
font_manager.fontManager.addfont('C:/Windows/Fonts/msyh.ttc')
plt.rcParams.update({'font.family':font_manager.FontProperties(fname='C:/Windows/Fonts/msyh.ttc').get_name(),'axes.unicode_minus':False,'font.size':10})
f=pd.read_csv(FOLDER/'observed_block_raw_and_derived.csv');t=pd.to_datetime(f['native_time'])
s=json.loads((FOLDER/'summary.json').read_text('utf-8'));high=pd.Timestamp(s['pair']['high_anchor']);low=pd.Timestamp(s['pair']['low_anchor'])
fig,axes=plt.subplots(3,1,figsize=(11,8),sharex=True,layout='constrained')
fig.suptitle('系统01 / 2019-06-18：失败片段的原始曲线核查',fontsize=15)
axes[0].plot(t,f['V_in_V'],color='#235789',lw=1,label='原始端口电压')
axes[0].axhline(164,color='#888888',ls=':',lw=.8,label='固定高压代理阈值164V')
axes[0].axhline(140,color='#aaaaaa',ls='--',lw=.8,label='固定低压代理阈值140V')
axes[0].set_ylabel('电压 / V');axes[0].legend(loc='center left',fontsize=9)
axes[1].plot(t,f['I_in_A'],color='#168575',lw=.9);axes[1].axhline(0,color='#999999',lw=.6);axes[1].set_ylabel('端口电流 / A\n充电为正')
axes[2].plot(t,f['P_in_W']/1000,color='#b8474d',lw=.85,label='发布P列')
axes[2].plot(t,f['UI_reconstructed_W']/1000,color='#235789',lw=.8,alpha=.8,label='原始U×I')
axes[2].set_ylabel('功率 / kW\n充电为正');axes[2].legend(loc='upper left',fontsize=9)
for ax in axes:
    ax.axvspan(high,low,color='#e0a43d',alpha=.15);ax.axvline(high,color='#b78119',ls='--',lw=.8);ax.axvline(low,color='#b78119',ls='--',lw=.8)
    ax.grid(alpha=.18);ax.spines[['top','right']].set_visible(False)
axes[0].text(high,166.2,'高端确认 01:30:49',ha='left',va='bottom',fontsize=9)
axes[0].text(low,141,'低端确认 02:36:55',ha='center',va='bottom',fontsize=9)
axes[2].xaxis.set_major_locator(mdates.MinuteLocator(byminute=[0,30]));axes[2].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
axes[2].set_xlabel('作者原生时间；逐秒绘制；阴影为原冻结积分区间，非已证明满空循环')
fig.savefig(OUT,dpi=150,facecolor='white');plt.close(fig)
(FOLDER/'figure_receipt.json').open('x',encoding='utf-8').write(json.dumps({'path':OUT.name,'sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),
    'source_sha256':hashlib.sha256((FOLDER/'observed_block_raw_and_derived.csv').read_bytes()).hexdigest(),'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'plot':'all 12188 native second rows; no resampling; original selected endpoint markers','matplotlib':matplotlib.__version__},ensure_ascii=False,indent=2))
print(str(OUT.resolve()))
