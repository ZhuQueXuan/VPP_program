"""Canonical renderer rasterization of the native Word-exported PDF.

Windows runtime has no bundled LibreOffice. Conversion is already performed
by Microsoft Word on the exact DOCX; use its PDF for canonical PNG inspection.
"""
import os,sys,importlib.util
import uuid
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[1]
renderer=Path(r'C:\Users\刘文轩\.codex\plugins\cache\openai-primary-runtime\documents\26.1020.11618\skills\documents\render_docx.py')
poppler=Path(r'C:\Users\刘文轩\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin')
os.environ['PATH']=str(poppler)+os.pathsep+os.environ.get('PATH','')
spec=importlib.util.spec_from_file_location('canonical_docx_renderer',renderer);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
docx=ROOT/'outputs/课题一B1与B2算法阶段汇报_20261029.docx';pdf=docx.with_suffix('.pdf')
def native_pdf(*args,**kwargs):return str(pdf),'Native Microsoft Word export; see word_export.json. No LibreOffice or network used.'
mod.convert_to_pdf=native_pdf
class RetainedScratch:
    """Respect repository no-delete policy; keep renderer scratch in work."""
    def __init__(self,prefix='',**kwargs):
        self.name=str(BASE/'renderer_scratch'/(prefix+uuid.uuid4().hex[:8]));Path(self.name).mkdir(parents=True,exist_ok=True)
    def __enter__(self):return self.name
    def __exit__(self,*args):return False
mod.tempfile.TemporaryDirectory=RetainedScratch
mod.rasterize(str(docx),str(BASE/'render_v2'),150,False,False)
print('All pages rasterized using canonical render_docx.py and native Word PDF')
