"""Use canonical renderer with the exact Word-native PDF; retain scratch per repository rules."""
import os,sys,uuid,importlib.util
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
renderer=Path(r'C:\Users\刘文轩\.codex\plugins\cache\openai-primary-runtime\documents\26.1020.11618\skills\documents\render_docx.py')
poppler=Path(r'C:\Users\刘文轩\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin')
os.environ['PATH']=str(poppler)+os.pathsep+os.environ.get('PATH','')
spec=importlib.util.spec_from_file_location('format_canonical_renderer',renderer);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
docx=ROOT/'outputs/课题一B1至B3算法阶段研究报告_20261029.docx';pdf=docx.with_suffix('.pdf')
def native_pdf(*args,**kwargs):return str(pdf),'Exact native Word PDF; see word_export.json. Windows runtime has no LibreOffice.'
mod.convert_to_pdf=native_pdf
class RetainedScratch:
    def __init__(self,prefix='',**kwargs):self.name=str(BASE/'renderer_scratch'/(prefix+uuid.uuid4().hex[:8]));Path(self.name).mkdir(parents=True,exist_ok=True)
    def __enter__(self):return self.name
    def __exit__(self,*args):return False
mod.tempfile.TemporaryDirectory=RetainedScratch
mod.rasterize(str(docx),str(BASE/(sys.argv[1] if len(sys.argv)>1 else 'render_v1')),150,False,False)
print('Formatted Word PDF rasterized through render_docx.py')
