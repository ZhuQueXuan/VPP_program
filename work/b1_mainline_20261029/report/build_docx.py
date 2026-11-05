"""Build the formal B1 report using bundled document dependencies and native math."""
from pathlib import Path
import copy, hashlib, json, re
from lxml import etree
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[3];BASE=Path(__file__).resolve().parent
SOURCE=ROOT/'04_汇报与调研资料/课题一B1算法研究报告_通用方法对比版_20261029.md'
OUT=ROOT/'outputs/课题一B1算法研究报告_通用方法对比版_20261029.docx'
M='http://www.w3.org/1998/Math/MathML'
xsl=etree.XSLT(etree.parse(r'C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL'))

def el(tag,*children,text=None):
 e=etree.Element('{'+M+'}'+tag)
 if text is not None:e.text=str(text)
 for c in children:e.append(c)
 return e
def i(s):return el('mi',text=s)
def o(s):return el('mo',text=s)
def n(s):return el('mn',text=s)
def row(*x):return el('mrow',*x)
def sub(x,s):return el('msub',x,i(s))
def hat(x):return el('mover',x,o('^'))
def frac(a,b):return el('mfrac',a,b)
def par(*a):return row(o('('),*a,o(')'))
def fun(x):return par(sub(i('X'),'i'))

def equations(kind):
 if kind==0:
  integ=el('msubsup',o('∫'),sub(i('a'),'k'),sub(i('b'),'k'))
  return [row(sub(i('r'),'k'),o('='),frac(n(1),row(sub(i('b'),'k'),o('−'),sub(i('a'),'k'))),
       integ,i('f'),par(i('t'),o(';'),i('θ')),i('dt'),o('+'),sub(i('ε'),'k'))]
 if kind==1:
  summ=el('munder',o('∑'),row(i('k'),o('⊂'),sub(i('W'),'i')))
  top=row(summ,par(hat(sub(i('B'),'ik')),o('−'),sub(i('P'),'ik')),
              par(sub(i('b'),'ik'),o('−'),sub(i('a'),'ik')))
  return [row(hat(sub(i('η'),'i')),o('='),frac(top,row(sub(i('q'),'i'),o('|'),sub(i('W'),'i'),o('|'))))]
 summ=el('munderover',o('∑'),row(i('i'),o('='),n(1)),i('n'))
 md=lambda:row(hat(sub(i('m'),'d')),fun('X'))
 ed=row(hat(sub(i('e'),'d')),fun('X'))
 correction=row(frac(row(i('1'),par(sub(i('D'),'i'),o('='),i('d'))),ed),
                 par(sub(i('Y'),'i'),o('−'),md()))
 return [row(hat(sub(i('μ'),'d')),o('='),frac(n(1),i('n')),summ,o('['),md(),o('+'),correction,o(']')),
         row(hat(sub(i('τ'),'d')),o('='),hat(sub(i('μ'),'d')),o('−'),hat(sub(i('μ'),'0')))]

def plain(s):
 s=s.replace('\\(','').replace('\\)','')
 for a,b in [('\\widehat',''),('\\theta','θ'),('\\varepsilon','ε'),('\\eta','η'),('\\mu','μ'),('\\tau','τ'),('\\mathbf1','1'),('\\subset','⊂'),('\\,',''),('\\','')]:s=s.replace(a,b)
 s=s.replace('{','').replace('}','').replace('_','').replace('**','').replace('`','')
 return s

doc=Document();sec=doc.sections[0]
sec.page_width=Cm(21);sec.page_height=Cm(29.7)
sec.top_margin=Cm(2.0);sec.bottom_margin=Cm(2.0);sec.left_margin=Cm(2.2);sec.right_margin=Cm(2.2)
for name in ['Normal','Title','Heading 1','Heading 2','Heading 3','Caption']:
 st=doc.styles[name];st.font.name='Times New Roman';st.font.color.rgb=RGBColor(0,0,0)
 st._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'宋体')
 st.paragraph_format.space_before=Pt(0);st.paragraph_format.space_after=Pt(0)
 st.paragraph_format.line_spacing=1.25
 for border in list(st.element.iter(qn('w:pBdr'))):border.getparent().remove(border)
doc.styles['Normal'].font.size=Pt(10.5);doc.styles['Normal'].paragraph_format.first_line_indent=Pt(21)
for name,size in [('Title',18),('Heading 1',14),('Heading 2',12),('Heading 3',10.5)]:
 st=doc.styles[name];st.font.size=Pt(size);st.font.bold=True
 st._element.rPr.rFonts.set(qn('w:eastAsia'),'黑体')
 st.paragraph_format.first_line_indent=Pt(0);st.paragraph_format.keep_with_next=True
 st.paragraph_format.page_break_before=False
doc.styles['Caption'].font.size=Pt(10);doc.styles['Caption'].font.bold=False
doc.styles['Caption'].paragraph_format.first_line_indent=Pt(0)
doc.styles['Caption'].paragraph_format.keep_with_next=False
foot=sec.footer.paragraphs[0];foot.alignment=WD_ALIGN_PARAGRAPH.CENTER
f=OxmlElement('w:fldSimple');f.set(qn('w:instr'),'PAGE');foot._p.append(f)
doc.core_properties.author='刘文轩';doc.core_properties.title='课题一B1响应过程识别与多档激励效应研究报告'
doc.core_properties.subject='CPOP与多档AIPW通用方法比较及RIDE成分适配'

def add_table(lines):
 cells=lambda x:[plain(y.strip()) for y in x.strip().strip('|').split('|')]
 headings=cells(lines[0]);data=[cells(l) for l in lines[2:]]
 table=doc.add_table(rows=1,cols=len(headings));table.autofit=False
 available=16.6
 widths=([6.6]+[(available-6.6)/(len(headings)-1)]*(len(headings)-1)) if len(headings)==4 else [4.7]+[(available-4.7)/(len(headings)-1)]*(len(headings)-1)
 for j,w in enumerate(widths):table.columns[j].width=Cm(w)
 for j,text in enumerate(headings):table.rows[0].cells[j].text=text
 for values in data:
  for cell,text in zip(table.add_row().cells,values):cell.text=text
 borders=OxmlElement('w:tblBorders')
 for side in ['top','left','bottom','right','insideH','insideV']:
  edge=OxmlElement('w:'+side);edge.set(qn('w:val'),'single');edge.set(qn('w:sz'),'4');edge.set(qn('w:color'),'D9D9D9');borders.append(edge)
 table._tbl.tblPr.append(borders)
 for ri,r in enumerate(table.rows):
  pr=r._tr.get_or_add_trPr();pr.append(OxmlElement('w:cantSplit'))
  if ri==0:pr.append(OxmlElement('w:tblHeader'))
  for j,c in enumerate(r.cells):
   c.width=Cm(widths[j]);tcpr=c._tc.get_or_add_tcPr()
   v=OxmlElement('w:vAlign');v.set(qn('w:val'),'center');tcpr.append(v)
   mar=OxmlElement('w:tcMar')
   for side in ['top','bottom','left','right']:
    edge=OxmlElement('w:'+side);edge.set(qn('w:w'),'70');edge.set(qn('w:type'),'dxa');mar.append(edge)
   tcpr.append(mar)
   if ri==0:
    sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'EEEEEE');tcpr.append(sh)
   for p in c.paragraphs:
    p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.keep_with_next=ri==len(table.rows)-1
    p.alignment=WD_ALIGN_PARAGRAPH.LEFT if j==0 else WD_ALIGN_PARAGRAPH.CENTER
    for run in p.runs:
     run.font.size=Pt(10.5);run.bold=ri==0
     if ri==0:run._element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),'黑体')

lines=SOURCE.read_text(encoding='utf-8').splitlines();idx=0;math_kind=0;figure_count=0
while idx<len(lines):
 line=lines[idx].strip();idx+=1
 if not line:continue
 if line=='\\[':
  while idx<len(lines) and lines[idx].strip()!='\\]':idx+=1
  idx+=1
  for formula in equations(math_kind):
   math=el('math',formula);native=xsl(math).getroot()
   p=doc.add_paragraph();p.paragraph_format.first_line_indent=Pt(0);p.alignment=WD_ALIGN_PARAGRAPH.CENTER
   mp=OxmlElement('m:oMathPara');mp.append(copy.deepcopy(native));p._p.append(mp)
  math_kind+=1;continue
 if line.startswith('|'):
  rows=[line]
  while idx<len(lines) and lines[idx].strip().startswith('|'):rows.append(lines[idx].strip());idx+=1
  add_table(rows);continue
 match=re.match(r'!\[([^]]*)\]\(([^)]+)\)',line)
 if match:
  path=(SOURCE.parent/match.group(2)).resolve();assert path.is_file(),path
  p=doc.add_paragraph();p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.keep_with_next=True;p.alignment=WD_ALIGN_PARAGRAPH.CENTER
  p.add_run().add_picture(str(path),width=Cm(16.3));figure_count+=1;continue
 match=re.match(r'^(#{1,4})\s+(.*)',line)
 if match:
  level=len(match.group(1));p=doc.add_paragraph(plain(match.group(2)),'Title' if level==1 else 'Heading '+str(level-1))
  if level==1:p.alignment=WD_ALIGN_PARAGRAPH.CENTER
  continue
 if re.match(r'^[图表]\d+ ',line):
  p=doc.add_paragraph(plain(line),'Caption');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;continue
 p=doc.add_paragraph(plain(line))
 if line.startswith('刘文轩'):p.paragraph_format.first_line_indent=Pt(0);p.alignment=WD_ALIGN_PARAGRAPH.CENTER
 if line.startswith('['):p.paragraph_format.first_line_indent=Pt(0)

doc.save(OUT)
from zipfile import ZipFile
with ZipFile(OUT) as z:
 xml=z.read('word/document.xml')
 tree=etree.fromstring(xml)
 ns={'m':'http://schemas.openxmlformats.org/officeDocument/2006/math','w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
 assert len(tree.xpath('//m:oMath',namespaces=ns))==4
 assert len(tree.xpath('//w:drawing',namespaces=ns))==4
receipt={'docx':str(OUT),'source':str(SOURCE),'native_math_equations':4,'figures':figure_count,'tables':len(doc.tables),
 'docx_sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
 'format':{'body_pt':10.5,'body_zh':'宋体','latin':'Times New Roman','headings':'黑体','line_spacing':1.25,'first_line_indent_pt':21,'caption_pt':10,'caption_bold':False,'forced_page_breaks':False}}
(BASE/'build_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False))
