"""Fetch a bounded explicit plan; preserve failures, never overwrite attempts."""
from common import *
import argparse,datetime,urllib.request,time
from urllib.parse import urlsplit
ap=argparse.ArgumentParser();ap.add_argument('--plan',required=True);ap.add_argument('--attempt',required=True)
a=ap.parse_args();assert Path(a.plan).name==a.plan and Path(a.attempt).name==a.attempt
pp=BASE/a.plan;p=load(pp);out=BASE/'downloads'/a.attempt;out.mkdir(parents=True,exist_ok=False)
receipt={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan_sha256':sha(pp),'files':[]}
for item in p['files']:
    assert urlsplit(item['url']).hostname in {'zenodo.org','www.nature.com'}
    assert Path(item['name']).name==item['name']
    row=dict(item);started=time.monotonic()
    try:
        req=urllib.request.Request(item['url'],headers={'User-Agent':'VPP-HVAC-source-audit/1.0'})
        md5=hashlib.md5();h=hashlib.sha256();n=0
        with urllib.request.urlopen(req,timeout=25) as r,(out/item['name']).open('xb') as f:
            row.update(http_status=r.status,final_url=r.url,content_type=r.headers.get('Content-Type'))
            while True:
                chunk=r.read(1048576)
                if not chunk:break
                n+=len(chunk);assert n<=item['limit_bytes'],'Explicit download limit exceeded'
                f.write(chunk);md5.update(chunk);h.update(chunk)
                assert time.monotonic()-started<240,'Download wall-clock limit exceeded'
        if 'expected_bytes' in item:assert n==item['expected_bytes']
        if 'expected_md5' in item:assert md5.hexdigest()==item['expected_md5']
        row.update(status='downloaded',bytes=n,sha256=h.hexdigest(),md5=md5.hexdigest())
    except Exception as e:row.update(status='failed',error=repr(e))
    row['elapsed_s']=time.monotonic()-started;receipt['files'].append(row);dump(out/'receipt.json',receipt)
    print(json.dumps(row,ensure_ascii=False),flush=True)
