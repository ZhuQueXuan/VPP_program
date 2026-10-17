"""Bounded official downloads, normal TLS, immutable attempt directories."""
from common import *
import argparse,urllib.request,urllib.parse,time,datetime
ap=argparse.ArgumentParser();ap.add_argument('--plan',required=True);ap.add_argument('--attempt',required=True);a=ap.parse_args()
assert Path(a.plan).name==a.plan and Path(a.attempt).name==a.attempt
plan=load(BASE/a.plan);out=BASE/'downloads'/a.attempt;out.mkdir(parents=True,exist_ok=False)
receipt={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan_sha256':sha(BASE/a.plan),'files':[]}
allowed={'data.mendeley.com','api.crossref.org','www.sciencedirect.com','engrxiv.org','www.mdpi.com','arxiv.org','www.ebi.ac.uk'}
for item in plan['files']:
    assert urllib.parse.urlsplit(item['url']).hostname in allowed and Path(item['name']).name==item['name']
    row=dict(item);start=time.monotonic()
    try:
        req=urllib.request.Request(item['url'],headers={'User-Agent':'VPP-water-heating-source-research/1.0'})
        h=hashlib.sha256();n=0
        with urllib.request.urlopen(req,timeout=30) as response,(out/item['name']).open('xb') as f:
            row.update(http_status=response.status,content_type=response.headers.get('Content-Type'),etag=response.headers.get('ETag'))
            while True:
                b=response.read(1048576)
                if not b:break
                n+=len(b);assert n<=item['limit_bytes'];f.write(b);h.update(b);assert time.monotonic()-start<300
        if 'expected_bytes' in item:assert n==item['expected_bytes']
        if 'expected_sha256' in item:assert h.hexdigest()==item['expected_sha256']
        row.update(status='downloaded',bytes=n,sha256=h.hexdigest())
    except Exception as e:row.update(status='failed',error=repr(e))
    row['elapsed_s']=time.monotonic()-start;receipt['files'].append(row);dump(out/'receipt.json',receipt);print(json.dumps(row,ensure_ascii=False),flush=True)
