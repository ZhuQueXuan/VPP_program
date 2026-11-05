"""Rasterize the exact native-Word PDF through the canonical document renderer."""
from pathlib import Path
import importlib.util, os, uuid
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[2]
renderer=Path(r'C:\Users\刘文轩\.codex\plugins\cache\openai-primary-runtime\documents\26.1020.11618\skills\documents\render_docx.py')
poppler=Path(r'C:\Users\刘文轩\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin')
os.environ['PATH']=str(poppler)+os.pathsep+os.environ.get('PATH','')
spec=importlib.util.spec_from_file_location('canonical_report_renderer',renderer)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
docx=ROOT/'outputs/课题一B1算法研究报告_通用方法对比版_20261029.docx'
pdf=docx.with_suffix('.pdf')
module.convert_to_pdf=lambda *a,**kw:(str(pdf),'Exact DOCX exported by Microsoft Word; word_export.json')
class Scratch:
 def __init__(self,prefix='',**kw):
  self.name=str(BASE/'scratch'/(prefix+uuid.uuid4().hex[:8]));Path(self.name).mkdir(parents=True,exist_ok=True)
 def __enter__(self):return self.name
 def __exit__(self,*a):return False
module.tempfile.TemporaryDirectory=Scratch
module.rasterize(str(docx),str(BASE/'render'),150,False,False)
print('Canonical renderer produced all page PNGs from native Word PDF.')
