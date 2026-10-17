"""Explicit public-source request plan, bounded transfer and provenance."""
from common import *
import argparse,urllib.request,time,datetime
from urllib.parse import urlsplit,urlunsplit
ap=argparse.ArgumentParser();ap.add_argument('--plan',required=True);ap.add_argument('--attempt',required=True);a=ap.parse_args()
assert Path(a.plan).name==a.plan and Path(a.attempt).name==a.attempt
pp=BASE/a.plan;plan=load(pp);out=BASE/'downloads'/a.attempt;out.mkdir(parents=True,exist_ok=False)
allowed={'data.mendeley.com','data.nlr.gov','eta-publications.lbl.gov','www.nlr.gov','api.datacite.org','public.mendeley.com','data.openei.org','creativecommons.org','openenergyhub.ornl.gov','api.crossref.org','papers.ssrn.com','sites.google.com','mathieu.engin.umich.edu','deepblue.lib.umich.edu'}
receipt={'date':'2026-10-16','started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan_sha256':sha(pp),'files':[]}
for item in plan['files']:
    assert urlsplit(item['url']).hostname in allowed,item['url']
    assert Path(item['name']).name==item['name']
    row=dict(item);started=time.monotonic()
    try:
        req=urllib.request.Request(item['url'],headers={'User-Agent':'VPP-HVAC-source-audit/1.0','Accept':'*/*'})
        n=0;h=hashlib.sha256();m=hashlib.md5()
        with urllib.request.urlopen(req,timeout=25) as r,(out/item['name']).open('xb') as f:
            split=urlsplit(r.url);row.update(http_status=r.status,content_type=r.headers.get('Content-Type'),final_url_without_query=urlunsplit((split.scheme,split.netloc,split.path,'','')),
                etag=r.headers.get('ETag'),last_modified=r.headers.get('Last-Modified'))
            while True:
                chunk=r.read(1048576)
                if not chunk:break
                n+=len(chunk);assert n<=item['limit_bytes'];f.write(chunk);h.update(chunk);m.update(chunk)
                assert time.monotonic()-started<240
        if 'expected_bytes' in item:assert n==item['expected_bytes']
        if 'expected_sha256' in item:assert h.hexdigest()==item['expected_sha256']
        if 'expected_sha1' in item:assert hashlib.sha1((out/item['name']).read_bytes()).hexdigest()==item['expected_sha1']
        row.update(status='downloaded',bytes=n,sha256=h.hexdigest(),md5=m.hexdigest())
    except Exception as e:row.update(status='failed',error=repr(e))
    row['elapsed_s']=time.monotonic()-started;receipt['files'].append(row);dump(out/'receipt.json',receipt)
    print(json.dumps(row,ensure_ascii=False),flush=True)
