"""Evidence inventory only. No process algorithm imports or model fitting."""
import csv,hashlib,json,math,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
EV=ROOT/'work/ev_charging_research_20261016'
ARCHIVE=ROOT/'data/public_datasets/德国_多特蒙德_电动汽车充电实验/dataset_merged.zip'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def native(v):
    if isinstance(v,np.generic):return v.item()
    if isinstance(v,np.ndarray):return v.tolist()
    if isinstance(v,dict):return {k:native(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [native(x) for x in v]
    return v
def write(name,v):
    p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(native(v),f,ensure_ascii=False,allow_nan=False,indent=2)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def num(v):
    try:a=float(v)
    except (TypeError,ValueError):return np.nan
    return a if np.isfinite(a) else np.nan

def main():
    sources=[ARCHIVE,EV/'downloads/KIT_LF_SOURCE_01/ev-charging_lf.parquet',EV/'downloads/KIT_LF_SOURCE_01/charging.csv',
        EV/'downloads/EV_SOURCE_03/measurements.csv',EV/'downloads/EV_NEXT_SOURCE_01/kit_zenodo_record.json']
    sources += [p for scope in ['B1算法','task','01_项目依据','work/b1_multiscale_evidence_20261031'] for p in (ROOT/scope).rglob('*') if p.is_file() and 'mpl_config' not in p.parts and '__pycache__' not in p.parts]
    sources += list((ROOT/'data/六类资源研究数据/03_电动汽车充电设施').rglob('*'))
    files=sorted(set(p for p in sources if p.is_file()))
    write('protected_before.json',{p.relative_to(ROOT).as_posix():sha(p) for p in files})
    write('protocol.json',dict(scope='Read-only audit of local execution/fault/cross-measurement evidence; first feature block, no algorithm edits.',
        cohorts='KIT existing LF/current+command; Dortmund all128 merged files for reported errors, metadata-matched25EVTEC AC dynamic files for AC cross-measurements. EPFL schema/minute-level control flags and local UrbanEV/ACN source role.',
        fault_dictionary='Publisher parameters.csv: STATE_ID2/3/4=9 Faulted, ChargeState_ID2/3/4=7 ended-with-error. STATE6/7 suspended is not fault. Unknown codes not interpreted.',
        fault_label_scope='Device-reported state; cannot label any same-row isolated electrical sample a sensor spike or exact fault onset.',
        cross_channel='AC only: grid P_kocos_200 and Type2 charger Output_Power_ID4, bothkW, same merged member/epoch. Separate channels, no assumed calibrated subsecond clocks. DC grid/output boundaries not equated.',
        candidate_windows='Consecutive |command step|>=.5kW returning within10s and previous/new settings equal on return, pre3s/post3s command steady, no timestamp reversal or gap>2s in whole window. Keep every candidate/status. For held decreases not returning within10s, no short-action label.',
        evidence_support='For candidateAC pulse, pre3s/during/post3s medians in each channel: direction-correct during change>=.3kW and>=20% commanded step, post median returns to within max(.3kW,30% observed shift) of pre. At least3 rows in each phase, Type2 STATE4 present during. Descriptive corroboration criteria, not calibrated causal/truth labels or baseline classifier.',
        exact_timing='No interpolation, sorting, sensor realignment, gap filling or denoising. Native indices and original CSV rows preserved.',
        simulation_fallback='If real labels inadequate for100ms, a small truth-known100ms evidence feasibility panel may be generated separately; same measurement grid for true actions and measurement faults, no CPOP/LABS fitting or new method selection.',
        stop='Do not infer labels from pulse length, outlier appearance, command proximity or model residual. No report/second block/default changes.'))
    print('source snapshot',len(files),flush=True)
if __name__=='__main__':main()
