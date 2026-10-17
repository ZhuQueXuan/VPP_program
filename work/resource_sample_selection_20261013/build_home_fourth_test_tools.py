"""Preserve prior frozen implementations while preparing final chronological test."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def save(name,s): (ROOT/name).open('x',encoding='utf-8',newline='\n').write(s)
s=(ROOT/'freeze_home_third_test_protocol.py').read_text('utf-8')
s=s.replace('rwth_home_third_test_20261014','rwth_home_fourth_test_20261014')
# First advance the old previous protocol, then the new destination filename.
s=s.replace("previous=json.loads((ROOT/'home_capacity_crossperiod_protocol_v2.json')", "previous=json.loads((ROOT/'home_capacity_crossperiod_protocol_v3.json')")
s=s.replace("PROTOCOL = ROOT/'home_capacity_crossperiod_protocol_v3.json'", "PROTOCOL = ROOT/'home_capacity_crossperiod_protocol_v4.json'")
s=s.replace('2019-07-01 13:55:06','2022-10-30 15:02:27')
s=s.replace("('01/2019_06_System_ID_01.csv','01/2019_07_System_ID_01.csv')", "('01/2022_10_System_ID_01.csv',)")
s=s.replace('CROSSPERIOD-v3','CROSSPERIOD-v4').replace('CROSSPERIOD-BL-v3','CROSSPERIOD-BL-v4').replace('DC-20261014-07','DC-20261014-09')
s=s.replace('June/July 2019','October 2022').replace('June history and July test diagnostics required','October history and test diagnostics required')
s=s.replace('rwth_home_id01_test_20190701T135506','rwth_home_id01_test_20221030T150227')
s=s.replace('published third chronological ID01 controlled test','published fourth chronological ID01 controlled test')
s=s.replace('v3 advances chronologically to third test','v4 advances chronologically to fourth and last listed test')
s=s.replace('earliest listed ID01 test after v2','earliest listed ID01 test after v3')
save('freeze_home_fourth_test_protocol.py',s)
for old,new in [('acquire_audit_home_third_test.py','acquire_audit_home_fourth_test.py'),('prepare_home_third_test_samples.py','prepare_home_fourth_test_samples.py'),('verify_home_third_test_samples.py','verify_home_fourth_test_samples.py'),('run_home_third_test_baselines.py','run_home_fourth_test_baselines.py'),('verify_home_third_test_baselines.py','verify_home_fourth_test_baselines.py')]:
    s=(ROOT/old).read_text('utf-8').replace('home_capacity_crossperiod_protocol_v3.json','home_capacity_crossperiod_protocol_v4.json')
    save(new,s)
print('Prepared fourth-event tools with identical numerical and unavailable-event rules; prior sources unchanged.')
