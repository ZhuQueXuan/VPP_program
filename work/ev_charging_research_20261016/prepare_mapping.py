"""Freeze all trial splits, same-row samples and exclusions before model errors."""
from mapping_common import *
from collections import Counter,defaultdict
import io,math,zipfile
out=BASE/'runs/PREP_EV_MAPPING_01';out.mkdir(parents=True,exist_ok=False)
pp=BASE/'common_command_mapping_protocol_v1.json';p=load(pp);assert sha(pp)==load(BASE/'common_command_mapping_freeze_v1.json')['protocol_sha256']
for s in p['sources'].values():assert sha(ROOT/s['path'])==s['sha256']
inv=read(ROOT/p['sources']['archive_inventory.csv']['path']);quality={r['member']:r for r in load(ROOT/p['sources']['dynamic_v1g_quality.json']['path'])}
cohort=[r for r in inv if r['type']=='ts_unidir_arbitrary_1' and r['station']=='EVTEC'];assert len(cohort)==48
groups=defaultdict(list)
for r in cohort:
    r['group']='|'.join(r[k] for k in ('vehicle','mode','plug_type'));groups[r['group']].append(r)
for key,rr in groups.items():
    rr.sort(key=lambda r:(quality[r['member']]['epoch_min'],r['member']));n=len(rr)//2;assert n>0
    assert max(quality[r['member']]['epoch_max'] for r in rr[:n])<min(quality[r['member']]['epoch_min'] for r in rr[n:]),key
    for i,r in enumerate(rr):r['split']='train' if i<n else 'test'
assert len(groups)==15
samples=[];coverage=[]
def f(s):
    try:v=float(s)
    except (ValueError,TypeError):return None
    return v if math.isfinite(v) else None
with zipfile.ZipFile(ROOT/p['sources']['archive']['path']) as z:
    for meta in sorted(cohort,key=lambda r:r['member']):
        with z.open(meta['member']) as stream:
            reader=csv.reader(io.TextIOWrapper(stream,encoding='utf-8-sig',newline=''),delimiter=';')
            header=next(r for r in reader if r);units=next(r for r in reader if r);idx={k:i for i,k in enumerate(header)}
            assert dict(zip(header,units))['P_kocos_200']=='kW'
            previous=None;watermark=None;blockstart=None;count=0;accepted=0;flags_count=Counter()
            for r in reader:
                if not r:continue
                count+=1;flags=[];t=f(r[idx['epoch']]);y=f(r[idx['P_kocos_200']]);us=[f(r[idx['AC_Power_set_ID'+str(i)]]) for i in (2,3,4)]
                if t is None:flags.append('epoch_nonfinite');blockstart=None
                else:
                    increasing=watermark is None or t>watermark
                    stepok=previous is None or 0<t-previous<=2000
                    if not increasing:flags.append('epoch_not_new_high')
                    if not stepok:flags.append('epoch_step_not_continuous')
                    if previous is None or not increasing or not stepok or blockstart is None:blockstart=t if increasing else None
                    if blockstart is None or t-blockstart<5000:flags.append('clock_warmup')
                    watermark=t if watermark is None else max(t,watermark)
                previous=t
                if any(v is None for v in us):flags.append('command_nonfinite')
                elif not us[0]==us[1]==us[2]:flags.append('commands_not_common')
                elif us[0]<0:flags.append('negative_command_not_V1G')
                if y is None:flags.append('grid_power_nonfinite')
                row={'member':meta['member'],'record_index':count,'vehicle':meta['vehicle'],'mode':meta['mode'],'plug_type':meta['plug_type'],
                    'group':meta['group'],'split':meta['split'],'epoch_ms':t if t is not None else '',
                    'command_ID2_kW':us[0] if us[0] is not None else '', 'command_ID3_kW':us[1] if us[1] is not None else '',
                    'command_ID4_kW':us[2] if us[2] is not None else '', 'common_command_kW':us[0] if all(v is not None for v in us) and us[0]==us[1]==us[2] else '',
                    'actual_grid_kW':y if y is not None else '', 'status':'admitted' if not flags else 'excluded','flags':'|'.join(flags)}
                samples.append(row);accepted+=not flags;flags_count.update(flags)
        assert count==quality[meta['member']]['rows']
        coverage.append({'member':meta['member'],'group':meta['group'],'split':meta['split'],'mode':meta['mode'],'raw_rows':count,
                         'samples':accepted,'fraction':accepted/count,'flags':dict(flags_count)})
for key in groups:
    for split in ('train','test'):assert any(r['status']=='admitted' and r['group']==key and r['split']==split for r in samples),(key,split)
table(out/'samples.csv',samples);dump(out/'coverage.json',coverage)
dump(out/'trial_split.json',[{k:r[k] for k in ('member','group','split','mode','vehicle','plug_type')} for r in sorted(cohort,key=lambda r:r['member'])])
summary={'date':'2026-10-16','raw_rows':len(samples),'groups':len(groups),'trials':len(cohort),
 'train_trials':sum(r['split']=='train' for r in cohort),'test_trials':sum(r['split']=='test' for r in cohort),
 'samples_by_split':dict(Counter(r['split'] for r in samples if r['status']=='admitted')),
 'samples_by_mode_split':dict(Counter(r['mode']+'_'+r['split'] for r in samples if r['status']=='admitted')),
 'excluded_flags':dict(Counter(f for r in samples for f in r['flags'].split('|') if f)),
 'interpretation':'Same-row command mapping without interpreting state/connector codes. All current source row values assumed complete; not operational control.'}
dump(out/'summary.json',summary)
dump(out/'admission.json',{'status':'limited_common_command_static_mapping_only','date':'2026-10-16','protocol_sha256':sha(pp),'before_fit_and_errors':True,
    'script_sha256':sha(Path(__file__)),'outputs':{f.name:sha(f) for f in sorted(out.iterdir())}})
print(json.dumps(summary,ensure_ascii=False,indent=2))
