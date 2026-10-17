"""One bounded HTTPS client compatibility retry; no TLS verification bypass."""
from pathlib import Path
import hashlib,json,sys,time
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
sys.path.insert(0,str(ROOT/'work/python_packages/pvlib_smart_20261015'))
import requests
out=BASE/'downloads/EV_SOURCE_03';out.mkdir(parents=True,exist_ok=False)
p=json.loads((BASE/'source_plan_v1.json').read_text());receipt=[]
for s in p['files'][:3]:
    e=dict(s)
    try:
        with requests.get(s['url'],headers={'User-Agent':'VPP-EV-source-research/1.0'},timeout=(10,20),stream=True) as r:
            e['http_status']=r.status_code
            if r.status_code==429:
                e['retry_after']=r.headers.get('Retry-After');e['status']='rate_limited';receipt.append(e);break
            r.raise_for_status();buf=[];size=0
            for chunk in r.iter_content(65536):
                size+=len(chunk);assert size<=s['limit_bytes'];buf.append(chunk)
            content=b''.join(buf);(out/s['name']).write_bytes(content)
            e.update(status='downloaded',bytes=len(content),sha256=hashlib.sha256(content).hexdigest(),md5=hashlib.md5(content).hexdigest())
    except Exception as error:e.update(status='failed',error=repr(error))
    receipt.append(e);print(json.dumps(e),flush=True)
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    time.sleep(2)
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
