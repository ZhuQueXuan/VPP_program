"""One new source attempt after the previous limited attempt ended."""
from pathlib import Path
import hashlib,json,sys
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
sys.path.insert(0,str(ROOT/'work/python_packages/pvlib_smart_20261015'))
import requests
OUT=BASE/'downloads/EV_SOURCE_04';OUT.mkdir(parents=True,exist_ok=False)
plan=[('parameters.csv','https://zenodo.org/records/14065331/files/parameters.csv?download=1',300000),
      ('record.json','https://zenodo.org/api/records/14065331',1000000)]
receipt=[]
for name,url,limit in plan:
    row={'name':name,'url':url,'limit_bytes':limit}
    try:
        with requests.get(url,timeout=(10,20),stream=True,headers={'User-Agent':'VPP-EV-source-research/1.0'}) as r:
            row.update(http_status=r.status_code,retry_after=r.headers.get('Retry-After'))
            if r.status_code==429:
                row['status']='rate_limited';receipt.append(row);break
            r.raise_for_status();content=r.raw.read(limit+1);assert len(content)<=limit
            (OUT/name).write_bytes(content)
            row.update(status='downloaded',bytes=len(content),sha256=hashlib.sha256(content).hexdigest(),md5=hashlib.md5(content).hexdigest())
    except Exception as e:row.update(status='failed',error=repr(e))
    receipt.append(row);print(json.dumps(row),flush=True)
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
