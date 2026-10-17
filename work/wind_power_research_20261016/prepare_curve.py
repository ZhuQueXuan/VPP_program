"""Source-order core quality and fixed whole-time split; no fit/error."""
from common import *
import argparse,zipfile,io,datetime,math,collections
ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);a=ap.parse_args();assert Path(a.run_id).name==a.run_id
out=BASE/'runs'/a.run_id;out.mkdir(exist_ok=False);pp=BASE/'curve_protocol_v1.json';p=load(pp);assert sha(pp)==load(BASE/'curve_freeze_v1.json')['protocol_sha256']
archive=ROOT/p['archive']['path'];assert sha(archive)==p['archive']['sha256']
counts=collections.Counter();splitcounts=collections.Counter();meta=[]
with (out/'candidates.csv').open('w',encoding='utf-8',newline='') as dest,zipfile.ZipFile(archive) as z:
    w=csv.DictWriter(dest,fieldnames=['unit','row','timestamp','wind_mps','power_kW','split','wind_invalid','power_invalid','clock_invalid','time_duplicate','time_outside','admitted']);w.writeheader()
    for name,info in sorted(p['members'].items()):
        seen=set();prev=None
        with io.TextIOWrapper(z.open(name),encoding='utf-8-sig',newline='') as f:
            comments=[next(f).rstrip() for _ in range(9)];assert '# Time zone: UTC' in comments
            reader=csv.DictReader(f);assert reader.fieldnames[0]=='# Date and time'
            for n,r in enumerate(reader,1):
                t=datetime.datetime.strptime(r['# Date and time'],'%Y-%m-%d %H:%M:%S').replace(tzinfo=datetime.timezone.utc)
                wind=float(r['Wind speed (m/s)']);power=float(r['Power (kW)']);outside=not datetime.datetime(2018,1,1,tzinfo=datetime.timezone.utc)<=t<datetime.datetime(2019,1,1,tzinfo=datetime.timezone.utc)
                flags={'wind_invalid':not math.isfinite(wind) or wind<0,'power_invalid':not math.isfinite(power),'clock_invalid':prev is not None and (t-prev).total_seconds()!=600,'time_duplicate':t in seen,'time_outside':outside};admitted=not any(flags.values())
                split='training' if t<datetime.datetime(2018,10,1,tzinfo=datetime.timezone.utc) else 'test'
                row={'unit':info['unit'],'row':n,'timestamp':t.isoformat(),'wind_mps':wind if math.isfinite(wind) else '', 'power_kW':power if math.isfinite(power) else '', 'split':split,**flags,'admitted':admitted};w.writerow(row)
                counts['candidates']+=1;counts['admitted']+=int(admitted)
                for k,v in flags.items():counts[k]+=int(v)
                if admitted:splitcounts[f"{split}_unit{info['unit']}"]+=1
                prev=t;seen.add(t)
        meta.append({'member':name,'rows':n});assert n==info['rows']
dump(out/'summary.json',{'counts':dict(counts),'split_counts':dict(splitcounts),'members':meta,'scope':p['state_scope']})
dump(out/'admission.json',{'status':'prepared_before_fitting','protocol_sha256':sha(pp),'preparer_sha256':sha(Path(__file__)),'outputs':{f.name:sha(f) for f in sorted(out.iterdir()) if f.is_file()}})
print(json.dumps({'counts':dict(counts),'split_counts':dict(splitcounts)},ensure_ascii=False,indent=2))
