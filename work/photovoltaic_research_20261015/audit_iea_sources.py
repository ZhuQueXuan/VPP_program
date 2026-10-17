"""Read the publisher-defined year and lab parameters; no model predictions/errors."""
from pathlib import Path
from datetime import datetime, timedelta
import csv
import hashlib
import json
import math
from openpyxl import load_workbook

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def numeric(x):
    try:
        v=float(x);return v if math.isfinite(v) else None
    except (TypeError,ValueError):return None

def main():
    out=BASE/'runs/IEA_SOURCE_QA_01';out.mkdir(parents=True,exist_ok=False)
    sources=[];csvsources=[]
    for folder in ('IEA_MODULE_SOURCES_01','IEA_MODULE_YEAR_01'):
        receipt=json.loads((BASE/'downloads'/folder/'receipt.json').read_text())
        for f in receipt['files']:
            path=BASE/'downloads'/folder/f['name']
            assert f['status']=='downloaded' and sha(path)==f['sha256'],f['name']
            item={'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'url':f['url'],'bytes':path.stat().st_size}
            sources.append(item)
            if path.suffix=='.csv':csvsources.append(item)
    assert len(csvsources)==12 and len({Path(f['path']).stem for f in csvsources})==12
    wb=load_workbook(BASE/'downloads/IEA_MODULE_SOURCES_01/module_characterization.xlsx',data_only=True,read_only=True)
    assert wb.sheetnames==['61853-1 & 2'];sheet=wb[wb.sheetnames[0]]
    assert sheet['A10'].value==1000 and sheet['C8'].value==25 and sheet['K8'].value=='δ [%/°C]'
    params={'technology':sheet['B1'].value,'p0_W':sheet['C10'].value,'gamma_per_C':sheet['K9'].value/100,
            'p0_cell':'C10 (G=1000 W/m2, T=25 C)', 'gamma_cell':'K9 with K8 percent/C',
            'sheet':sheet.title,'temperature_reference_C':25,
            'thermal_U0':sheet['U9'].value,'thermal_U1':sheet['V9'].value,
            'note':'Published lab measurements, not fitted to outdoor power; indoor/outdoor asserted same module by publisher, serial not exposed. Back temperature is not cell temperature.'}
    dump(out/'lab_parameters.json',params)
    fields=['Pm','Voc','Isc','Tbom','Gpoa','Gglob_hor','Gdiff_hor','RH_AIR','AIR_TEMP','WIND_SPEED']
    monthly=[];alltimes=set();detail=[]
    for src in sorted(csvsources,key=lambda x:Path(x['path']).name):
        path=ROOT/src['path']
        with path.open(newline='',encoding='utf-8-sig') as f:
            rows=list(csv.DictReader(f,delimiter=';',skipinitialspace=True))
        times=[];badkeys=0;core=0;inconsistent=0;negative=0
        cols={k:[] for k in fields}
        for line,r in enumerate(rows,2):
            t=datetime.strptime(r['Date']+' '+r['Time'],'%d.%m.%Y %H:%M:%S')
            assert t.strftime('%Y_%m')==path.stem and t not in alltimes
            alltimes.add(t);times.append(t)
            d={k:numeric(r[k]) for k in fields}
            for k,v in d.items():
                if v is not None:cols[k].append(v)
            finite=all(d[k] is not None for k in ('Pm','Voc','Isc','Tbom','Gpoa'))
            core+=finite
            impossible=finite and (d['Pm']<0 or d['Voc']<=0 or d['Isc']<=0 or d['Pm']>d['Voc']*d['Isc']+0.001)
            inconsistent+=impossible
            negative+=d['Gpoa'] is not None and d['Gpoa']<0
            badkeys+=t.minute%5!=0 or t.second!=0
            detail.append({'source':src['path'],'line':line,'time':t.isoformat(sep=' '),
                           **d,'core_finite':finite,'iv_inconsistent':impossible})
        assert times==sorted(times)
        monthly.append({'month':path.stem,'rows':len(rows),'observed_dates':len({t.date() for t in times}),
                        'first':str(times[0]),'last':str(times[-1]),'off_five_minute':badkeys,
                        'core_finite':core,'iv_inconsistent_finite':inconsistent,'negative_G':negative,
                        'fields':{k:{'finite':len(v),'missing_or_nonfinite':len(rows)-len(v),
                                     'min':min(v) if v else None,'max':max(v) if v else None} for k,v in cols.items()}})
    with (out/'all_source_rows.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(detail[0]));writer.writeheader();writer.writerows(detail)
    expected={datetime(2018,7,1)+timedelta(minutes=5*i) for i in range(365*288)}
    summary={'status':'source_quality_read_complete_not_model_pass','source_count':len(sources),'months':monthly,
             'rows':sum(m['rows'] for m in monthly),'core_finite':sum(m['core_finite'] for m in monthly),
             'iv_inconsistent_finite':sum(m['iv_inconsistent_finite'] for m in monthly),
             'observed_dates':len({t.date() for t in alltimes}),'observed_exact_calendar_labels':len(alltimes&expected),
             'unrepresented_24h_calendar_labels':len(expected-alltimes),
             'coverage_note':'Source is sparse daytime-like I-V observations; absent labels not observed zero, and cannot infer full-year energy or missing-data mechanism.',
             'source_meaning':'Publisher Annex 1 physical pp164-165: simultaneous five-minute I-V, irradiance and module temperature; Pm extracted DC maximum power, not inverter AC or command tracking.',
             'license':'Publisher publicly offers an open-source validation data set for model comparison. No named CC/SPDX redistribution license found on page/workbook/Annex. Local research and aggregate results only; raw files not redistributed or relicensed.',
             'time_note':'Published naive clock labels; timezone/averaging windows not specified here. No UTC inference, time shift or energy integration.',
             'limits':['one anonymous mono-Si module, one site','back temperature, not observed cell temperature','POA is incident rather than fully corrected effective irradiance','not complete continuous year or night-output reference']}
    dump(out/'source_manifest.json',sources);dump(out/'summary.json',summary)
    dump(out/'receipt.json',{'script_sha256':sha(Path(__file__)),'outputs':{p.name:sha(p) for p in sorted(out.iterdir())}})
    print(json.dumps({k:v for k,v in summary.items() if k!='months'},ensure_ascii=False,indent=2))
    print('Month counts:',[(m['month'],m['rows'],m['core_finite'],m['iv_inconsistent_finite']) for m in monthly])

if __name__=='__main__':main()
