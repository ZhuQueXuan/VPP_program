"""Read-only inventory of first-party endpoint evidence; no capacity calculation."""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import io
import json
import math
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parent
pa=argparse.ArgumentParser();pa.add_argument('--run-id',required=True);a=pa.parse_args()
if not a.run_id.isidentifier():raise ValueError('simple unique ID required')
BASE=ROOT/'downloads/rwth_home_endpoint_evidence_20261015';OUT=BASE/a.run_id
if OUT.exists():raise FileExistsError(OUT)
OLD=ROOT/'downloads/rwth_home_capacity_20261014'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old=json.loads((OLD/'method_acquisition_01.json').read_text('utf-8'))
new=json.loads((BASE/'acquisition_02.json').read_text('utf-8'))['sources']
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
keyword=re.compile(r'(?:start|end|duration|stop|soc|test|eoc|eod)',re.I)
target_serial=43647.579930555556

def inventory(raw,identity):
    result={'identity':identity,'sha256':hashlib.sha256(raw).hexdigest(),'worksheets':[]}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if z.testzip() is not None:raise ValueError('bad XLSX CRC')
        strings=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
        book=ET.fromstring(z.read('xl/workbook.xml'))
        result['date1904']=book.find('s:workbookPr',ns).attrib.get('date1904','false') if book.find('s:workbookPr',ns) is not None else 'false'
        result['defined_names']=[{'name':x.attrib.get('name'),'value':x.text} for x in book.findall('s:definedNames/s:definedName',ns)]
        rels={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        def value(c):
            v=c.findtext('s:v',default='',namespaces=ns)
            if c.attrib.get('t')=='s' and v:return strings[int(v)]
            if c.attrib.get('t')=='inlineStr':return ''.join(c.find('s:is',ns).itertext())
            return v
        for sheet in book.find('s:sheets',ns):
            target=rels[sheet.attrib['{'+ns['r']+'}id']]
            path=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join('xl',target))
            summary={'name':sheet.attrib['name'],'state':sheet.attrib.get('state','visible'),'xml_member':path,
                     'rows':0,'columns':{},'keyword_text_cells':[],'first_three_rows':[],
                     'target_time_numeric_cells':[],'last_populated_row':{}}
            with z.open(path) as handle:
                for event,row in ET.iterparse(handle,events=['end']):
                    if row.tag!='{'+ns['s']+'}row':continue
                    cells={c.attrib['r']:value(c) for c in row.findall('s:c',ns)}
                    summary['rows']+=1
                    if len(summary['first_three_rows'])<3:summary['first_three_rows'].append(cells)
                    summary['last_populated_row']=cells
                    for address,v in cells.items():
                        col=re.match('[A-Z]+',address).group()
                        cstat=summary['columns'].setdefault(col,{'header':v,'nonempty_cells':0,'numeric_cells_after_header':0,'numeric_min':None,'numeric_max':None})
                        if v and v.strip():cstat['nonempty_cells']+=1
                        if keyword.search(v):summary['keyword_text_cells'].append({'cell':address,'text':v})
                        try:numeric=float(v)
                        except (ValueError,TypeError):continue
                        if summary['rows']>1 and math.isfinite(numeric):
                            cstat['numeric_cells_after_header']+=1
                            cstat['numeric_min']=numeric if cstat['numeric_min'] is None else min(numeric,cstat['numeric_min'])
                            cstat['numeric_max']=numeric if cstat['numeric_max'] is None else max(numeric,cstat['numeric_max'])
                            if abs(numeric-target_serial)<1e-8:summary['target_time_numeric_cells'].append(address)
                    row.clear()
            result['worksheets'].append(summary)
        # Comments/drawings can contain endpoint definitions absent from cells.
        result['other_text_keyword_hits']=[]
        for name in z.namelist():
            if name.endswith('.xml') and any(part in name for part in ['comments','drawings','charts']):
                try:elements=ET.fromstring(z.read(name))
                except ET.ParseError:continue
                for element in elements.iter():
                    if element.tag.split('}')[-1] in ['t','v'] and element.text and keyword.search(element.text):
                        result['other_text_keyword_hits'].append({'member':name,'text':element.text})
    return result

books=[]
for index in range(1,7):
    name=f'publisher_source_{index:02}.xlsx';path=(BASE if index in [2,4] else OLD)/name
    evidence=new[name] if index in [2,4] else old[name]
    if sha(path)!=evidence['sha256']:raise ValueError('source fingerprint changed: '+name)
    books.append(inventory(path.read_bytes(),name))
meta=ROOT/'downloads/independent_candidates_20261013/rwth_home_metadata.zip'
with zipfile.ZipFile(meta) as z:
    for name in ['00_Data/00_Metadata/Capacity_Tests.xlsx','00_Data/00_Metadata/Metadata_Systems.xlsx']:
        books.append(inventory(z.read(name),name))
    matlab=[name for name in z.namelist() if name.lower().endswith('.m')]
    code_hits=[]
    for name in matlab:
        for line_no,line in enumerate(z.read(name).decode('utf-8',errors='replace').splitlines(),1):
            if re.search(r'(?:test|soc|end.?time|stop.?time|duration)',line,re.I):
                code_hits.append({'member':name,'line':line_no,'text':line})
pdf=OLD/'supplementary_information.pdf'
if sha(pdf)!=old['supplementary_information.pdf']['sha256']:raise ValueError('PDF changed')
reader=PdfReader(pdf)
relevant_pages={str(i+1):reader.pages[i].extract_text() for i in [3,4,10,11,12,16]}
OUT.mkdir()
(OUT/'workbook_inventory.json').write_text(json.dumps(books,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'publisher_code_keyword_hits.json').write_text(json.dumps({'zip_sha256':sha(meta),'matlab_members_scanned':len(matlab),'hits':code_hits,'code_executed':False},ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'pdf_relevant_pages.json').write_text(json.dumps({'path':str(pdf.resolve()),'sha256':sha(pdf),'physical_pages':relevant_pages},ensure_ascii=False,indent=2),encoding='utf-8')
summary={'run_id':a.run_id,'client_date':'2026-10-15','workbooks':len(books),'worksheets':sum(len(b['worksheets']) for b in books),
         'source_files':{str(((BASE if i in [2,4] else OLD)/f'publisher_source_{i:02}.xlsx').relative_to(ROOT)):sha((BASE if i in [2,4] else OLD)/f'publisher_source_{i:02}.xlsx') for i in range(1,7)},
         'metadata_zip_sha256':sha(meta),'supplementary_pdf_sha256':sha(pdf),'all_sources_read_only':True,
         'new_capacity_integrals_predictions':False,'code_sha256':sha(Path(__file__)),
         'scope':'six publisher workbooks plus two metadata workbooks; all worksheet values/headers/names, comments/drawings keyword scan; all bundled MATLAB code keyword scan; relevant method PDF pages',
         'caution':'field inventory supports bounded absence claims only; numeric array endings are not event-level SOC or test-end annotations'}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'receipt.json').write_text(json.dumps({'code_sha256':sha(Path(__file__)),'artifacts':{q.name:sha(q) for q in OUT.iterdir() if q.is_file()}},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
for b in books:
    if b['identity'] in ['publisher_source_03.xlsx','00_Data/00_Metadata/Capacity_Tests.xlsx','publisher_source_04.xlsx']:
        print(json.dumps({'identity':b['identity'],'sheets':[{'name':s['name'],'rows':s['rows'],'headers':{k:v['header'] for k,v in s['columns'].items()},'target_time_cells':s['target_time_numeric_cells']} for s in b['worksheets']]},ensure_ascii=False))
