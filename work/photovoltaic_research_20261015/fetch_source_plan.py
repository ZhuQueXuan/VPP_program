"""Download only explicitly planned public PV source files, with per-file limits."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
from urllib.parse import urlsplit
import urllib.request

BASE=Path(__file__).resolve().parent
ALLOWED={'oedi-data-lake.s3.amazonaws.com','raw.githubusercontent.com','data.openei.org','catalog.data.gov',
         'www.solarelectricsupply.com','pvlib-python.readthedocs.io','pvpmc.sandia.gov',
         'www.osti.gov','docs.nlr.gov'}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--plan',type=Path,required=True)
    args=parser.parse_args()
    plan=json.loads(args.plan.read_text(encoding='utf-8'))
    out=BASE/'downloads'/plan['id']
    out.mkdir(parents=True,exist_ok=False)
    receipt={'id':plan['id'],'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'plan_sha256':hashlib.sha256(args.plan.read_bytes()).hexdigest(),'files':[]}
    for item in plan['files']:
        url=item['url'];name=item['name'];limit=item.get('limit_bytes',2_000_000)
        assert urlsplit(url).scheme=='https' and urlsplit(url).hostname in ALLOWED
        assert Path(name).name==name and 0<limit<=10_000_000
        entry={'name':name,'url':url}
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'VPP-PV-research-source-check'})
            with urllib.request.urlopen(req,timeout=40) as response:
                data=response.read(limit+1)
                entry.update(http_status=response.status,content_type=response.headers.get('Content-Type'),
                             etag=response.headers.get('ETag'))
            if len(data)>limit:raise ValueError('Planned byte limit exceeded')
            (out/name).write_bytes(data)
            entry.update(status='downloaded',bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        except Exception as error:
            entry.update(status='failed',error=repr(error))
        receipt['files'].append(entry)
        print(json.dumps(entry,ensure_ascii=False),flush=True)
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False),encoding='utf-8')

if __name__=='__main__':main()
