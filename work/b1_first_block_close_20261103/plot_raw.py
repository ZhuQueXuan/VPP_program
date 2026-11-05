from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
rows=read(HERE/'real_test/samples.json');folder=HERE/'real_test/review_pages';folder.mkdir(exist_ok=True)
for page in range((len(rows)+3)//4):
    fig,axes=plt.subplots(4,2,figsize=(16,12),sharex=True)
    for j,r in enumerate(rows[page*4:page*4+4]):
        t=np.asarray(r['relative_seconds']);ax,bx=axes[j]
        ax.plot(t,r['current_a'],'o-',ms=3,lw=1,label='Recorded current (A)');ax.step(t,r['pilot_a'],where='post',lw=1,alpha=.65,label='Reported limit (A)');bx.plot(t,r['power_kw'],'o-',ms=3,lw=1,color='black',label='Recorded power (kW)')
        for a in [ax,bx]:
            a.axvline(0,color='red',lw=.8,ls='--');a.grid(alpha=.25);a.set_xlim(-60,180);a.legend(fontsize=8)
            for k in np.flatnonzero(np.diff(t)>15):a.axvspan(t[k],t[k+1],color='gray',alpha=.2)
        ax.set_title(f"Case{r['case']} | {r['stratum']} | step{r['pilot_delta_a']:.2f}A | hold{r['limit_hold_seconds']:.1f}s",fontsize=10,loc='left');bx.set_title('Original observations; grey indicates gap>15s',fontsize=10,loc='left')
    for a in axes[-1]:a.set_xlabel('Seconds relative to selected limit change/background anchor')
    fig.tight_layout();fig.savefig(folder/f'page_{page+1:02d}.png',dpi=120);plt.close(fig)
print('Raw review pages:',(len(rows)+3)//4,flush=True)
