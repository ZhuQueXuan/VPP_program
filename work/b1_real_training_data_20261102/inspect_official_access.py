from pathlib import Path
import requests,json
from html.parser import HTMLParser
HERE=Path(__file__).resolve().parent
class Scripts(HTMLParser):
    def __init__(self):super().__init__();self.sources=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='script' and a.get('src'):self.sources.append(a['src'])
try:
    r=requests.get('https://ev.caltech.edu/dataset.html',timeout=(10,20));r.raise_for_status();(HERE/'source_documents/acn_official_page.html').write_text(r.text,encoding='utf-8');h=Scripts();h.feed(r.text)
    out=dict(scripts=h.sources,download_lines=[x.strip()[:250] for x in r.text.splitlines() if 'download' in x.lower()][:15]);print(json.dumps(out),flush=True)
except Exception as ex:out=dict(error=str(ex));print(json.dumps(out),flush=True)
(HERE/'official_access_inspection.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
