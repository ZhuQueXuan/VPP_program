"""Explicit primary URLs, bounded downloads and publisher-checksum provenance."""
from common import *
import argparse,urllib.request,time,datetime
from urllib.parse import urlsplit,urlunsplit
ap=argparse.ArgumentParser();ap.add_argument('--plan',required=True);ap.add_argument('--attempt',required=True);a=ap.parse_args()
assert Path(a.plan).name==a.plan and Path(a.attempt).name==a.attempt
planpath=BASE/a.plan;plan=load(planpath);out=BASE/'downloads'/a.attempt;out.mkdir(parents=True,exist_ok=False)
allowed={'zenodo.org','www.mdpi.com','onlinelibrary.wiley.com','api.crossref.org','arxiv.org','wes.copernicus.org'}
r={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan_sha256':sha(planpath),'files':[]}
for item in plan['files']:
    assert urlsplit(item['url']).hostname in allowed and Path(item['name']).name==item['name']
    row=dict(item);start=time.monotonic()
    try:
        request=urllib.request.Request(item['url'],headers={'User-Agent':'VPP-wind-source-research/1.0','Accept':'*/*'})
        h=hashlib.sha256();md5=hashlib.md5();n=0
        with urllib.request.urlopen(request,timeout=30) as response,(out/item['name']).open('xb') as f:
            u=urlsplit(response.url);row.update(http_status=response.status,content_type=response.headers.get('Content-Type'),etag=response.headers.get('ETag'),final_url_without_query=urlunsplit((u.scheme,u.netloc,u.path,'','')))
            while True:
                block=response.read(1048576)
                if not block:break
                n+=len(block);assert n<=item['limit_bytes'];f.write(block);h.update(block);md5.update(block);assert time.monotonic()-start<420
        if 'expected_bytes' in item:assert n==item['expected_bytes']
        if 'expected_md5' in item:assert md5.hexdigest()==item['expected_md5']
        row.update(status='downloaded',bytes=n,sha256=h.hexdigest(),md5=md5.hexdigest())
    except Exception as e:row.update(status='failed',error=repr(e))
    row['elapsed_s']=time.monotonic()-start;r['files'].append(row);dump(out/'receipt.json',r);print(json.dumps(row,ensure_ascii=False),flush=True)
