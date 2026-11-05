"""Real ordinary AC charging traces and independent grid PQA, original order."""
from pathlib import Path
import csv,io,json,zipfile,math,collections
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent

def num(v):
    try:x=float(v)
    except (TypeError,ValueError):return None
    return x if math.isfinite(x) else None

def main():
    inventory=json.loads((ROOT/'work/b1_execution_evidence_20261031/dortmund_files.json').read_text())
    selected=[r for r in inventory if r['mode']=='AC' and r['type']=='charging'];archive=ROOT/'data/public_datasets/德国_多特蒙德_电动汽车充电实验/dataset_merged.zip';summary=[];out=[]
    with zipfile.ZipFile(archive) as z:
      for meta in selected:
        with z.open(meta['member']) as stream:
            r=csv.reader(io.TextIOWrapper(stream,encoding='utf-8-sig',newline=''),delimiter=';');header=next(r);units=next(r);idx={k:i for i,k in enumerate(header)}
            power_column='P_kocos_210' if meta['station']=='Wirelane' else 'P_kocos_200'
            fields=[k for k in ['epoch',power_column,'AC_Power_set_ID4','Output_Power_ID4','STATE_ID4','ChargeState_ID4'] if k in idx]
            assert 'epoch' in idx and power_column in idx
            assert units[idx[power_column]].strip()=='kW',(meta['member'],units[idx[power_column]])
            bins={};origin=None;last=None;back=0;bad=0
            for line,row in enumerate(r,3):
                if len(row)!=len(header):bad+=1;continue
                t=num(row[idx['epoch']]);p=num(row[idx[power_column]])
                if t is None:bad+=1;continue
                if origin is None:origin=t
                gap=0 if last is None else t-last;back+=int(gap<0);last=t;m=int(math.floor((t-origin)/60000))
                b=bins.setdefault(m,dict(n=0,finite_n=0,sum_kw=0.,first_epoch_ms=t,last_epoch_ms=t,max_gap_ms=0.,first_source_line=line,last_source_line=line,commands=[],backward_steps=0))
                b['n']+=1;b['last_epoch_ms']=t;b['last_source_line']=line;b['max_gap_ms']=max(b['max_gap_ms'],gap)
                b['backward_steps']+=int(gap<0)
                if p is not None:b['finite_n']+=1;b['sum_kw']+=p
                if 'AC_Power_set_ID4' in idx:
                    v=num(row[idx['AC_Power_set_ID4']])
                    if v is not None:b['commands'].append(v)
        rr=[]
        for m,b in sorted(bins.items()):
            row=dict(recording=meta['member'],vehicle=meta['member'].split('/')[0],station=meta['station'],origin_ms=origin,minute=m,
                power_kw=b['sum_kw']/b['finite_n'] if b['finite_n'] else None,raw_n=b['n'],finite_n=b['finite_n'],first_epoch_ms=b['first_epoch_ms'],last_epoch_ms=b['last_epoch_ms'],max_gap_ms=b['max_gap_ms'],
                command_min=min(b['commands']) if b['commands'] else None,command_max=max(b['commands']) if b['commands'] else None,first_source_line=b['first_source_line'],last_source_line=b['last_source_line'],backward_steps=b['backward_steps'])
            rr.append(row)
        out+=rr;summary.append(dict(member=meta['member'],mode='AC',type='ordinary_charging',station=meta['station'],source_rows=sum(x['raw_n'] for x in rr),minute_rows=len(rr),duration_minutes=(last-origin)/60000 if origin is not None else 0,backward_timestamps=back,bad_rows=bad,power_unit='kW',power_column=power_column,available_context_columns=fields))
    (HERE/'dortmund_minutes_checked.json').write_text(json.dumps(out),encoding='utf-8');(HERE/'dortmund_coverage_checked.json').write_text(json.dumps(summary),encoding='utf-8')
    print(json.dumps([dict(member=r['member'],duration_minutes=round(r['duration_minutes'],1),minutes=r['minute_rows'],back=r['backward_timestamps']) for r in summary]),flush=True)
if __name__=='__main__':main()
