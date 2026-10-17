"""Independent pandas reading of the prospective EVTEC raw members."""
from pathlib import Path
from collections import Counter
import csv,hashlib,json,sys,zipfile
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
for d in ('work/teacher_storage_brief_20261014/plot_dependencies','work/python_packages/storage_ecm_20261015','work/python_packages/pvlib_smart_20261015'):
    sys.path.insert(0,str(ROOT/d))
import pandas as pd
import numpy as np
run=BASE/'runs/EV_SOURCE_QA_02';dest=run/'verification.json';assert not dest.exists()
qa=json.loads((run/'summary.json').read_text());receipt=json.loads((run/'receipt.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert all(sha(run/n)==h for n,h in receipt['outputs'].items())
assert all(sha(ROOT/n)==h for n,h in receipt['source_documents'].items())
archive=ROOT/qa['archive_path'];assert sha(archive)==qa['archive_sha256']
meta=pd.read_csv(BASE/'downloads/EV_SOURCE_03/measurements.csv',sep=';',keep_default_na=False)
assert len(meta)==142 and meta.meas_name.str.casefold().nunique()==142
inv=pd.read_csv(run/'archive_inventory.csv',keep_default_na=False)
quality=json.loads((run/'dynamic_v1g_quality.json').read_text());rawmap={r['member']:r for r in quality}
cohort=inv[(inv.type=='ts_unidir_arbitrary_1')&(inv.station=='EVTEC')]
assert len(cohort)==48 and cohort.power_unit.eq('kW').all()
checks=0;time_anomalies=[]
with zipfile.ZipFile(archive) as z:
    names=sorted(n for n in z.namelist() if n.endswith('_e.csv'))
    assert names==sorted(inv.member.tolist())
    for r in cohort.itertuples(index=False):
        with z.open(r.member) as f:
            df=pd.read_csv(f,sep=';',skiprows=[1],usecols=lambda c:c in ('epoch','P_kocos_200') or c.startswith('AC_Power_set_ID'))
        s=rawmap[r.member];assert len(df)==s['rows'];delta=df.epoch.diff().dropna()
        values={'backward_epoch_steps':int(sum(delta<0)),'duplicate_epoch_steps':int(sum(delta==0)),
                'gaps_over_2000ms':int(sum(delta>2000)),'grid_power_min_kW':float(df.P_kocos_200.min()),
                'grid_power_max_kW':float(df.P_kocos_200.max()),'epoch_min':float(df.epoch.min()),'epoch_max':float(df.epoch.max())}
        for key,v in values.items():assert abs(v-s[key])<1e-9;checks+=1
        assert np.isfinite(df.P_kocos_200).all() and np.isfinite(df.epoch).all()
        for col in [c for c in df if c.startswith('AC_Power_set_ID')]:
            d=s['command_ranges'][col]
            assert df[col].min()==d['min'] and df[col].max()==d['max'] and df[col].nunique()==d['distinct_values'];checks+=3
        if (delta<0).any():
            time_anomalies.append({'member':r.member,'backward_steps':int(sum(delta<0)),'minimum_signed_step_ms':float(delta.min()),
                                   'maximum_step_ms':float(delta.max())})
evrows=sum(rawmap[n]['rows'] for n in cohort.member)
missing=sorted(set(meta.meas_name.str.casefold())-set(Path(n).name[:-6].casefold() for n in names))
unknown=sorted(set(Path(n).name[:-6].casefold() for n in names)-set(meta.meas_name.str.casefold()))
assert len(missing)==15 and len(unknown)==1
result={'status':'passed_for_source_quality_only','independent_reader':'pandas raw ZIP members vs stdlib csv audit',
 'archive_sha256':sha(archive),'raw_members':128,'metadata_trials':142,'unmatched_archive_member':unknown,
 'metadata_without_exact_member':len(missing),'EVTEC_files':48,'EVTEC_rows':evrows,
 'EVTEC_modes':dict(Counter(cohort['mode'])),'EVTEC_grid_and_command_units':'kW in source unit rows',
 'EVTEC_nonfinite_grid_power':0,'EVTEC_nonfinite_epoch':0,'numeric_checks':checks,
 'EVTEC_backward_steps':sum(r['backward_steps'] for r in time_anomalies),'backward_time_trials':time_anomalies,
 'EVTEC_gaps_over_2000ms':sum(rawmap[n]['gaps_over_2000ms'] for n in cohort.member),
 'schema_note':'Across all65 filename-recognized V1G files, the audit count88353 unavailable P_kocos_200 entries is a requested-field count, mostly whole absent columns in Wirelane/unmapped files; not88353 verified missing sensor observations. Do not combine schemas.',
 'model_admission':'pending official state/connector semantics, chronology policy and frozen samples/protocol; no model errors computed',
 'verifier_sha256':sha(Path(__file__))}
dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
