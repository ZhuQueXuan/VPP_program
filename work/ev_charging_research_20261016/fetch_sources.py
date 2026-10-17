"""Read bounded, explicitly listed official public EV source files only."""
from pathlib import Path
import argparse,datetime,hashlib,json,urllib.request
from urllib.parse import urlsplit
BASE=Path(__file__).resolve().parent
ALLOWED={'zenodo.org','eldorado.tu-dortmund.de','ev.caltech.edu'}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);a=ap.parse_args()
    assert Path(a.attempt).name==a.attempt
    plan=BASE/'source_plan_v1.json';p=json.loads(plan.read_text())
    out=BASE/'downloads'/a.attempt;out.mkdir(parents=True,exist_ok=False)
    receipt={'date':'2026-10-16','started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan_sha256':hashlib.sha256(plan.read_bytes()).hexdigest(),'files':[]}
    for s in p['files']:
        assert urlsplit(s['url']).scheme=='https' and urlsplit(s['url']).hostname in ALLOWED
        assert Path(s['name']).name==s['name'] and s['limit_bytes']<=10_000_000
        e={**s}
        try:
            req=urllib.request.Request(s['url'],headers={'User-Agent':'VPP-EV-source-research/1.0'})
            with urllib.request.urlopen(req,timeout=35) as r:
                assert urlsplit(r.url).hostname in ALLOWED
                content=r.read(s['limit_bytes']+1);assert len(content)<=s['limit_bytes']
                e.update(http_status=r.status,content_type=r.headers.get('Content-Type'),resolved_url=r.url)
            (out/s['name']).write_bytes(content)
            e.update(status='downloaded',bytes=len(content),sha256=hashlib.sha256(content).hexdigest(),md5=hashlib.md5(content).hexdigest())
        except Exception as error:e.update(status='failed',error=repr(error))
        receipt['files'].append(e)
        (out/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(e,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
