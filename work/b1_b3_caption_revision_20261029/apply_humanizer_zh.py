from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
from lxml import etree as E
import copy,difflib,hashlib,json,re

BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
q=lambda n:'{'+NS['w']+'}'+n
sha=lambda b:hashlib.sha256(b).hexdigest()
text=lambda p:''.join(p.xpath('.//w:t/text()',namespaces=NS))
canon=lambda p:E.tostring(p,method='c14n')
numeric=lambda s:re.findall(r'[-−+]?\d+(?:\.\d+)?',s)
english=lambda s:re.findall(r'[A-Za-z][A-Za-z0-9_]*',s)

def replace_preserving_runs(par,new):
    nodes=par.xpath('.//w:t',namespaces=NS)
    arr=[n.text or '' for n in nodes];old=''.join(arr);offsets=[];pos=0
    for s in arr:offsets.append((pos,pos+len(s)));pos+=len(s)
    for tag,a,b,c,d in reversed(difflib.SequenceMatcher(None,old,new,autojunk=False).get_opcodes()):
        if tag=='equal':continue
        start=next((i for i,(lo,hi) in enumerate(offsets) if lo<=a<hi),len(nodes)-1)
        end=next((i for i,(lo,hi) in enumerate(offsets) if lo<b<=hi),start) if b>a else start
        aa=a-offsets[start][0];bb=b-offsets[end][0]
        if start==end:arr[start]=arr[start][:aa]+new[c:d]+arr[start][bb:]
        else:
            arr[start]=arr[start][:aa]+new[c:d]
            for i in range(start+1,end):arr[i]=''
            arr[end]=arr[end][bb:]
    assert ''.join(arr)==new
    for n,s in zip(nodes,arr):
        n.text=s
        if s.startswith(' ') or s.endswith(' '):n.set('{http://www.w3.org/XML/1998/namespace}space','preserve')

def without_text(el):
    x=copy.deepcopy(el)
    for t in x.xpath('.//w:t',namespaces=NS):
        t.text=''
        t.attrib.pop('{http://www.w3.org/XML/1998/namespace}space',None)
    return canon(x)

for folder in [BASE,ROOT/'work/b123_personal_briefing_20261029']:
    s=json.loads((folder/'humanizer_zh_source.json').read_text(encoding='utf-8'))
    target=Path(s['target']);raw=(folder/'before_humanizer_zh.docx').read_bytes()
    assert sha(raw)==s['before_sha256']
    assert sha(target.read_bytes())==s['before_sha256'],'User edits detected; rebase first'
    proposals=json.loads((folder/'humanizer_zh_accepted.json').read_text(encoding='utf-8'))
    assert len({p['index'] for p in proposals})==len(proposals)
    sources={p['index']:p for p in s['paragraphs']}
    for p in proposals:
        assert sources[p['index']]['editable'] and sources[p['index']]['text']==p['old']
        assert p['old']!=p['new']
        assert numeric(p['old'])==numeric(p['new']),('numbers',p['index'])
        assert english(p['old'])==english(p['new']),('terms',p['index'])
    z=ZipFile(BytesIO(raw));xml=z.read('word/document.xml');doc=E.fromstring(xml);body=doc.find('w:body',NS)
    by_index={p['index']:p for p in proposals};modified={}
    for i,p in by_index.items():
        original=body[i];assert text(original)==p['old'];candidate=copy.deepcopy(original)
        replace_preserving_runs(candidate,p['new'])
        assert without_text(original)==without_text(candidate),'Formatting or non-prose changed'
        modified[p['old']]=candidate
    nsdecl=b' '.join(('xmlns:'+prefix+'="'+uri+'"').encode() for prefix,uri in doc.nsmap.items() if prefix)
    ops=[]
    for m in re.finditer(rb'<w:p(?:\s[^>]*)?>.*?</w:p>',xml,re.S):
        try:p=E.fromstring(b'<root '+nsdecl+b'>'+m.group()+b'</root>')[0]
        except E.XMLSyntaxError:continue
        old=text(p)
        if old not in modified:continue
        frag=E.tostring(modified[old],encoding='unicode',with_tail=False)
        frag=re.sub(r' xmlns(?::[\w]+)?="[^"]*"','',frag).encode('utf-8')
        ops.append((m.start(),m.end(),frag))
    assert len(ops)==len(proposals),'Ambiguous paragraph identity'
    newxml=xml
    for a,b,frag in sorted(ops,reverse=True):newxml=newxml[:a]+frag+newxml[b:]
    after=E.fromstring(newxml);ab=after.find('w:body',NS);assert len(body)==len(ab)
    for i,(a,b) in enumerate(zip(body,ab)):
        if i in by_index:
            assert text(b)==by_index[i]['new'];assert without_text(a)==without_text(b)
        else:assert canon(a)==canon(b),('Untargeted content changed',i)
    for path in ['//w:tbl','//w:drawing','//m:oMath']:
        assert [canon(p) for p in doc.xpath(path,namespaces=NS)]==[canon(p) for p in after.xpath(path,namespaces=NS)],path
    out=BytesIO()
    with ZipFile(out,'w') as dest:
        for item in z.infolist():dest.writestr(copy.copy(item),newxml if item.filename=='word/document.xml' else z.read(item.filename))
    staged=folder/'humanizer_zh_staged.docx';staged.write_bytes(out.getvalue())
    with ZipFile(staged) as check:assert all(z.read(n)==check.read(n) for n in z.namelist() if n!='word/document.xml')
    receipt={k:v for k,v in s.items() if k!='paragraphs'}
    receipt.update({'staged':str(staged),'staged_sha256':sha(staged.read_bytes()),'changed_paragraphs':len(proposals),'accepted_changes':proposals,'numbers_and_english_tokens_preserved':True,'all_paragraph_and_run_formatting_preserved':True,'headings_captions_tables_formulas_media_references_preserved':True,'only_document_xml_text_changed':True})
    (folder/'humanizer_zh_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'humanizer_zh_staged_text.txt').write_text('\n'.join(text(p) for p in ab if text(p)),encoding='utf-8')
    export=(BASE/'methods_results_export.ps1').read_text(encoding='utf-8').replace(str(BASE),str(folder)).replace('methods_results_staged.docx','humanizer_zh_staged.docx').replace('methods_results_preview.pdf','humanizer_zh_preview.pdf').replace('methods_results_export.json','humanizer_zh_export.json')
    (folder/'humanizer_zh_export.ps1').write_text(export,encoding='utf-8')
    render=(BASE/'methods_results_render.py').read_text(encoding='utf-8').replace('methods_results_export.json','humanizer_zh_export.json').replace('methods_results_render','humanizer_zh_render')
    (folder/'humanizer_zh_render.py').write_text(render,encoding='utf-8')
    print(folder.name,len(proposals),'prose edits; protected structure and tokens unchanged')
