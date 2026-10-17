"""Bounded primary-source prefixes: field inspection, never full-file QA."""
from common import *
import re, urllib.request, datetime
from urllib.parse import urljoin
ap=__import__('argparse').ArgumentParser();ap.add_argument('--attempt',required=True);a=ap.parse_args()
assert Path(a.attempt).name==a.attempt
source=BASE/'downloads/SPLITSMART_PREVIEW_01/catalog.html'
links=list(dict.fromkeys(re.findall(r"href=['\"](/files/5971/[^'\"]+\.csv)['\"]",source.read_text(encoding='utf-8'))))
assert len(links)==13
out=BASE/'downloads'/a.attempt;out.mkdir(exist_ok=False)
receipt={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'catalog_sha256':sha(source),'purpose':'only first 16384 bytes of remaining eight data files; not complete download, no full-file count/checksum/clock claim','files':[]}
for link in links:
    name=Path(link).name
    if name.endswith('_context.csv') or name=='dataC108AC01.csv':continue
    item={'name':name,'url':urljoin('https://data.openei.org',link)}
    try:
        request=urllib.request.Request(item['url'],headers={'User-Agent':'VPP-HVAC-source-audit/1.0','Range':'bytes=0-16383'})
        with urllib.request.urlopen(request,timeout=25) as r:
            b=r.read(16384)
            item.update(http_status=r.status,content_range=r.headers.get('Content-Range'),content_length=r.headers.get('Content-Length'),etag=r.headers.get('ETag'))
        p=out/(name+'.prefix');p.write_bytes(b)
        item.update(status='prefix_only',bytes=len(b),prefix_sha256=sha(p),header=b.splitlines()[0].decode('utf-8-sig'),first_row=b.splitlines()[1].decode('utf-8-sig'))
    except Exception as e:item.update(status='failed',error=repr(e))
    receipt['files'].append(item);dump(out/'receipt.json',receipt)
    print(json.dumps({k:v for k,v in item.items() if k!='first_row'},ensure_ascii=False),flush=True)
assert len(receipt['files'])==8
