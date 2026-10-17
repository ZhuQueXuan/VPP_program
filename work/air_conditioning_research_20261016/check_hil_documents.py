"""Tie source document dates/names to five downloaded AC recordings."""
from common import *
from datetime import datetime,timedelta
import re
out=BASE/'runs/HIL_DOCUMENT_CHECK_01';out.mkdir(parents=True,exist_ok=False)
matrix=load(BASE/'runs/HIL_DOCUMENT_01/test_matrix_values.json')['xl/worksheets/sheet2.xml']
qa=load(BASE/'runs/HIL_AC_QA_01/file_quality.json');byfile={r['file']:r for r in qa}
matches=[]
for row in matrix[1:]:
    bycol={re.sub(r'\d+','',key):value for key,value in row.items()}
    file=bycol['F'];date=(datetime(1899,12,30)+timedelta(days=float(bycol['G']))).date().isoformat()
    assert file in byfile
    start_date=byfile[file]['first_timestamp'][:10];assert date==start_date
    matches.append({'test':bycol['A'],'file':file,'source_matrix_date':date,'raw_first_date':start_date,
                    'thermostat_setpoint_F':bycol['E'],'approximate_start_raw_cell':bycol['H']})
assert len(matches)==14 and len(set(r['file'] for r in matches))==5
dump(out/'matrix_file_date_checks.json',matches)
dump(out/'receipt.json',{'status':'passed','AC_matrix_rows':14,'distinct_AC_files':5,
 'all_matrix_dates_match_file_first_dates':True,'approximate_start_not_true_command_time':True,
 'PDF_visual_review':['HIL82562PDFp6: hardware vs simulated building schematic','six-buildings109149PDFp11: COP-derived cooling electricity'],
 'scope':'Platform validation paper concerns different3ton HP; no transfer of physical accuracy results to this2ton AC.',
 'source_files':{str(p.relative_to(ROOT)):sha(p) for p in [BASE/'downloads/HIL_AC_SOURCE_01/Test_Matrix.xlsx',BASE/'downloads/HIL_AC_SOURCE_01/hil_validation.pdf',BASE/'downloads/MATCHED_SOURCE_01/six_buildings_paper.pdf']},
 'script_sha256':sha(Path(__file__))})
print('14 AC matrix rows, five exact filenames and dates consistent; approximate times not used as command labels.')
