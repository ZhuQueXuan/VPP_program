"""Fetch the author's public SSRN link once, with a10MB response bound."""
from mapping_common import *
import urllib.request
url='https://papers.ssrn.com/sol3/Delivery.cfm/18906f4e-d423-462d-aea5-822cf9bb7024-MECA.pdf?abstractid=6265089&mirid=1'
out=BASE/'downloads/KIT_PAPER_01';out.mkdir(parents=True,exist_ok=False)
e={'url':url,'date':'2026-10-16','limit_bytes':10000000}
try:
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'VPP-EV-source-research/1.0'}),timeout=25) as r:
        b=r.read(10000001);assert len(b)<=10000000;e.update(http_status=r.status,content_type=r.headers.get('Content-Type'),final_url=r.url)
    file=out/('paper.pdf' if b.startswith(b'%PDF-') else 'response.html');file.write_bytes(b)
    e.update(status='downloaded_pdf' if b.startswith(b'%PDF-') else 'not_pdf_response',path=file.relative_to(ROOT).as_posix(),bytes=len(b),sha256=sha(file))
except Exception as error:e.update(status='failed',error=repr(error))
dump(out/'receipt.json',e);print(json.dumps(e))
