from pathlib import Path
import os,json,hashlib,importlib.util,uuid
BASE=Path(__file__).resolve().parent
renderer=Path(r'C:\Users\刘文轩\.codex\plugins\cache\openai-primary-runtime\documents\26.1020.11618\skills\documents\render_docx.py')
poppler=Path(r'C:\Users\刘文轩\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin')
os.environ['PATH']=str(poppler)+os.pathsep+os.environ.get('PATH','')
r=json.loads((BASE/'compensation_effect_wording_export.json').read_text(encoding='utf-8-sig'))
assert hashlib.sha256(Path(r['input']).read_bytes()).hexdigest()==r['input_sha256']
assert hashlib.sha256(Path(r['pdf']).read_bytes()).hexdigest()==r['pdf_sha256']
spec=importlib.util.spec_from_file_location('heading_renderer',renderer);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
mod.convert_to_pdf=lambda *args,**kwargs:(r['pdf'],'Word native PDF export verified against exact DOCX SHA')
class Scratch:
    def __init__(self,prefix='',**kwargs):self.name=str(BASE/'renderer_scratch'/(prefix+uuid.uuid4().hex[:8]));Path(self.name).mkdir(parents=True,exist_ok=True)
    def __enter__(self):return self.name
    def __exit__(self,*args):return False
mod.tempfile.TemporaryDirectory=Scratch
mod.rasterize(r['input'],str(BASE/'compensation_effect_wording_render'),130,False,False)
print('Rendered',r['page_count'],'pages')
