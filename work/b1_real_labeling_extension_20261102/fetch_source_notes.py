from pathlib import Path
import requests,json,hashlib
HERE=Path(__file__).resolve().parent;OUT=HERE/'source_documents';OUT.mkdir(exist_ok=True)
url='https://thesis.library.caltech.edu/14191/1/Lee_Zachary_J_2021_Thesis.pdf'
p=OUT/'Lee_Zachary_J_2021_Thesis.pdf'
try:
    raw=p.read_bytes() if p.exists() else requests.get(url,timeout=(10,35)).content
    assert raw.startswith(b'%PDF'),raw[:60]
    if not p.exists():p.write_bytes(raw)
    result=dict(status='downloaded',url=url,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
except Exception as ex:result=dict(status='failed',url=url,error=str(ex))
(OUT/'source_receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result),flush=True)
