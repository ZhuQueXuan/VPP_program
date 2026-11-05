from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
registry={r['event_id']:r for r in read(VIEW/'registry.json')};rows={r['event_id']:r for r in load('validation')};pred={r['event_id']:r for r in read(HERE/'validation/predictions.json')};curves=read(HERE/'validation/native_curves.json')
fig,axes=plt.subplots(2,2,figsize=(14,8))
evidence=[]
for row,case in enumerate([41,73]):
    key=next(k for k,v in registry.items() if v['case']==case);r=rows[key];a=arrays(r);c=context(a);p=pred[key]['methods'];ax,ix=axes[row]
    ax.plot(a['t'],a['p'],'o-',ms=3,lw=.8,color='black',label='original power (kW)');ax.plot(a['t'],curves[key]['cpop']['prediction'],lw=1.3,label='original CPOP');ax.plot(a['t'],curves[key]['labs']['prediction'],lw=1,alpha=.8,label='original LABS')
    ix.plot(a['t'],a['i'],'o-',ms=3,lw=.8,label='original current (A)');ix.step(a['t'],a['pilot'],where='post',lw=1,alpha=.7,label='reported limit (A)')
    base=p['candidate']['reference_recorded_power_kw'];tol=max(.03,2*c['sigma_p'])
    ax.axhspan(base-tol,base+tol,color='orange',alpha=.18,label='fixed return band')
    bracket=r['provisional_targets']['recovery_completion_bracket_seconds']
    if bracket:
        for z in [ax,ix]:z.axvspan(*bracket,color='green',alpha=.25,label='provisional reviewed return')
    for z in [ax,ix]:
        z.axvline(0,color='gray',ls='--',lw=1);z.grid(alpha=.25);z.set_xlim(-24,80 if case==41 else 32);z.set_xlabel('Original relative time (s)')
        if case==41:z.axvline(p['candidate']['recovery_seconds'],color='red',ls='--',label='candidate return')
        if case==73:z.axvline(p['candidate']['onset_seconds'],color='red',ls='--',label='candidate extra detection')
        z.legend(fontsize=8,loc='best')
    ax.set_title(f'Case {case}: '+('return rule waits too long' if case==41 else 'raw rescue adds a label-disagreement'))
    ix.set_title('Original channels; same EVSE, not independent fault truth')
    picks=(a['t']>=-24)&(a['t']<=16)
    evidence.append(dict(case=case,event_id=key,raw_rows=[dict(seconds=float(t),power_kw=float(v),current_a=float(i),pilot_a=float(l)) for t,v,i,l in zip(a['t'][picks],a['p'][picks],a['i'][picks],a['pilot'][picks])],candidate=p['candidate'],cpop=p['cpop'],raw_only=p['raw_only'],return_band_kw=[base-tol,base+tol],reviewed_recovery=bracket))
fig.tight_layout();fig.savefig(HERE/'diagnosis_examples.png',dpi=140);plt.close(fig)
save('source_diagnosis.json',dict(cases=evidence,no_refit_or_parameter_change=True))
print('Saved two raw-source diagnosis examples',flush=True)
