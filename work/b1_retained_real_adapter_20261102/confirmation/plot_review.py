from pathlib import Path
import json,math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent;rows=json.loads((HERE/'samples.json').read_text(encoding='utf-8'));OUT=HERE/'review_pages';OUT.mkdir(exist_ok=True)
for page in range(8):
    fig,axes=plt.subplots(4,2,figsize=(16,12),sharex=True)
    for j,s in enumerate(rows[page*4:page*4+4]):
        t=np.array(s['relative_seconds']);ax,bx=axes[j];ax.plot(t,s['current_a'],'o-',ms=2.7,lw=.8,label='current (A)');ax.step(t,s['pilot_a'],where='post',lw=1,alpha=.7,label='reported limit (A)');bx.plot(t,s['power_kw'],'o-',ms=2.7,lw=.8,color='black',label='power (kW)')
        for z in [ax,bx]:
            z.axvline(0,color='red',ls='--',lw=.8);z.grid(alpha=.25);z.set_xlim(-60,180);z.legend(fontsize=8)
            for k in np.flatnonzero(np.diff(t)>15):z.axvspan(t[k],t[k+1],color='grey',alpha=.2)
        ax.set_title(f"Case {s['case']} | {s['stratum']} | delta {s['pilot_delta_a']:.2f}A | hold {s['limit_hold_seconds']:.1f}s",fontsize=10,loc='left');bx.set_title('RAW ONLY | '+','.join(sorted({v for v in s['charging_state'] if v})),fontsize=9,loc='left')
    for z in axes[-1]:z.set_xlabel('Original seconds relative to reported-limit edge / background anchor')
    fig.tight_layout();fig.savefig(OUT/f'page_{page+33:02d}.png',dpi=125);plt.close(fig)
print('8 raw-only review pages created; no model inference',flush=True)
