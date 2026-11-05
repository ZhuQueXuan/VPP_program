from pathlib import Path
import json,math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent;rows=json.loads((HERE/'samples.json').read_text(encoding='utf-8'));folder=HERE/'review_pages';folder.mkdir(exist_ok=True)
for page in range(math.ceil(len(rows)/4)):
    fig,axes=plt.subplots(4,2,figsize=(16,12),sharex=True)
    for j,r in enumerate(rows[page*4:page*4+4]):
        t=np.asarray(r['relative_seconds']);current=np.asarray(r['current_a'],float);pilot=np.asarray(r['pilot_a'],float);power=np.asarray(r['power_kw'],float)
        ax,bx=axes[j];ax.plot(t,current,'o-',ms=2.6,lw=.9,label='measured current (A)');ax.step(t,pilot,where='post',lw=1,alpha=.65,label='reported limit (A)');bx.plot(t,power,'o-',ms=2.6,lw=.9,color='black',label='reported power (kW)')
        for a in [ax,bx]:a.axvline(0,color='red',lw=.8,ls='--');a.grid(alpha=.25);a.set_xlim(-60,180);a.legend(fontsize=8,loc='best');a.tick_params(labelsize=9)
        ax.set_title(f"Case {r['case']:02d} | {r['stratum']} | limit delta {r['pilot_delta_a']:.2f} A | hold {r['limit_hold_seconds']:.1f} s",fontsize=10,loc='left');bx.set_title('Original observations; no smoothing / proposed labels',fontsize=9,loc='left')
    for a in axes[-1]:a.set_xlabel('Seconds relative to first reported limit change / background anchor')
    fig.tight_layout();fig.savefig(folder/f'page_{page+1:02d}.png',dpi=125);plt.close(fig)
print('Review pages',math.ceil(len(rows)/4),flush=True)
