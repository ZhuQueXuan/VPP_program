"""One bounded metadata/document request per planned public URL."""
from mapping_common import *
import argparse,datetime,urllib.request
from urllib.parse import urlsplit
ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);a=ap.parse_args();assert Path(a.attempt).name==a.attempt
out=BASE/'downloads'/a.attempt;out.mkdir(parents=True,exist_ok=False)
plan=BASE/'next_source_plan_v1.json';entries=[]
for item in load(plan)['files']:
    assert urlsplit(item['url']).hostname in {'api.github.com','raw.githubusercontent.com','publikationen.bibliothek.kit.edu','zenodo.org'}
    row=dict(item)
    try:
        req=urllib.request.Request(item['url'],headers={'User-Agent':'VPP-EV-source-research/1.0'})
        with urllib.request.urlopen(req,timeout=20) as r:
            data=r.read(item['limit_bytes']+1);assert len(data)<=item['limit_bytes']
            row.update(http_status=r.status,content_type=r.headers.get('Content-Type'),etag=r.headers.get('ETag'))
        (out/item['name']).write_bytes(data)
        row.update(status='downloaded',bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    except Exception as e:row.update(status='failed',error=repr(e))
    entries.append(row);dump(out/'receipt.json',{'date':'2026-10-16','plan_sha256':sha(plan),'files':entries})
    print(json.dumps(row),flush=True)
