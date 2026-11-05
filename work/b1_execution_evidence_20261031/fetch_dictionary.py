"""Small official field dictionary, normal TLS, no bulk dataset download."""
from common import *
import urllib.request,hashlib,time
url='https://zenodo.org/records/14065331/files/parameters.csv?download=1'
try:
    request=urllib.request.Request(url,headers={'User-Agent':'evidence-audit/1.0'})
    with urllib.request.urlopen(request,timeout=25) as response:
        data=response.read(200001);status=response.status
    assert len(data)<=200000 and hashlib.md5(data).hexdigest()=='55a479a1a34114a81da6bbc233cda419'
    with (HERE/'parameters.csv').open('xb') as f:f.write(data)
    write('dictionary_fetch.json',dict(status='downloaded_verified',url=url,bytes=len(data),md5=hashlib.md5(data).hexdigest(),sha256=hashlib.sha256(data).hexdigest()))
except Exception as e:
    write('dictionary_fetch.json',dict(status='not_downloaded',url=url,error=type(e).__name__+':'+str(e),
        browser_primary_text_read=True,publisher_dictionary_codes=dict(STATE_ID2_3_4_faulted=9,ChargeState_ID2_3_4_ended_with_error=7),
        no_full_file_md5_verification=True))
print(json.dumps(read(HERE/'dictionary_fetch.json')))
