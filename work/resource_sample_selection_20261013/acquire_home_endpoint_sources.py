"""Download two explicitly identified publisher XLSX sources with strict size caps."""
from pathlib import Path
import argparse
import concurrent.futures
import hashlib
import json
import urllib.request

ROOT=Path(__file__).resolve().parent
pa=argparse.ArgumentParser();pa.add_argument('--receipt-id',required=True);a=pa.parse_args()
if not a.receipt_id.isidentifier():raise ValueError('simple unique ID required')
OUT=ROOT/'downloads/rwth_home_endpoint_evidence_20261015'
receipt=OUT/(a.receipt_id+'.json')
if receipt.exists():raise FileExistsError(receipt)
old=json.loads((ROOT/'downloads/rwth_home_capacity_20261014/method_acquisition_01.json').read_text('utf-8'))
def fetch(index):
    name=f'publisher_source_{index:02}.xlsx';url=old[name]['url'];path=OUT/name
    expected=f'https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41560-024-01620-9/MediaObjects/41560_2024_1620_MOESM{index+1}_ESM.xlsx'
    if url!=expected:raise ValueError('unexpected source URL')
    if path.exists():raise FileExistsError(path)
    result={'url':url,'byte_cap':25000000}
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'VPP-research-source-audit/1.0'})
        with urllib.request.urlopen(request,timeout=25) as response:
            if not response.url.startswith('https://media.springernature.com/'):raise ValueError('unexpected redirect domain')
            data=response.read(25000001)
            result.update(status=response.status,final_url=response.url,content_length_header=response.headers.get('Content-Length'))
        if len(data)>25000000:raise ValueError('source exceeds explicit 25MB cap')
        if not data.startswith(b'PK'):raise ValueError('not an XLSX archive')
        path.open('xb').write(data)
        result.update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),local_path=str(path.resolve()))
    except Exception as exc:result['error']=str(exc)
    return name,result
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=dict(pool.map(fetch,[2,4]))
receipt.open('x',encoding='utf-8').write(json.dumps({'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'sources':results},ensure_ascii=False,indent=2))
print(json.dumps(results,ensure_ascii=False))
