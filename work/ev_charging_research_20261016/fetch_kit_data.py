"""Acquire the necessary LF dataset only; never fetch the22GB HF file."""
from mapping_common import *
import datetime,urllib.request,hashlib,time
out=BASE/'downloads/KIT_LF_SOURCE_01';out.mkdir(parents=True,exist_ok=False)
record=load(BASE/'downloads/EV_NEXT_SOURCE_01/kit_zenodo_record.json')
assert record['id']==17866847 and record['metadata']['version']=='1.0.0'
assert record['metadata']['license']['id']=='cc-by-4.0'
chosen=[f for key in ('charging.csv','ev-charging_lf.parquet') for f in record['files'] if f['key']==key]
assert len(chosen)==2 and sum(f['size'] for f in chosen)<423000000
entries=[]
for f in chosen:
    row={'name':f['key'],'url':f['links']['self'],'expected_bytes':f['size'],'expected_checksum':f['checksum']}
    started=time.monotonic();file=out/f['key'];md5=hashlib.md5();h=hashlib.sha256();size=0
    try:
        req=urllib.request.Request(row['url'],headers={'User-Agent':'VPP-EV-source-research/1.0'})
        with urllib.request.urlopen(req,timeout=45) as r,file.open('xb') as stream:
            row.update(http_status=r.status,content_type=r.headers.get('Content-Type'),etag=r.headers.get('ETag'))
            while True:
                chunk=r.read(1024*1024)
                if not chunk:break
                size+=len(chunk);assert size<=f['size'];stream.write(chunk);h.update(chunk);md5.update(chunk)
                if size%(64*1024*1024)==0:print(json.dumps({'name':f['key'],'bytes_received':size,'total_bytes':f['size']}),flush=True)
        assert size==f['size'] and 'md5:'+md5.hexdigest()==f['checksum']
        row.update(status='downloaded_and_checksum_verified',bytes=size,sha256=h.hexdigest(),md5=md5.hexdigest())
    except Exception as error:row.update(status='failed_keep_partial',bytes=size,error=repr(error))
    row['elapsed_seconds']=time.monotonic()-started;entries.append(row)
    dump(out/'receipt.json',{'date':'2026-10-16','source_record_sha256':sha(BASE/'downloads/EV_NEXT_SOURCE_01/kit_zenodo_record.json'),'files':entries})
    print(json.dumps(row),flush=True)
