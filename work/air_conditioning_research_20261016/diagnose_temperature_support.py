"""Describe fitted-feature support; no new fitting, filtering or scores."""
from common import *
import sys
sys.path.insert(0,str(ROOT/'work/python_packages/pv_metadata_20261015'))
import duckdb
out=BASE/'runs/TEMPERATURE_SUPPORT_01';out.mkdir(parents=True,exist_ok=False)
con=duckdb.connect();source=str(BASE/'runs/PREP_TEMPERATURE_01/all_candidates.parquet')
cur=con.execute('''SELECT block,room,split,count(*) AS rows,sum((state=1)::INT) AS on_rows,
 sum((state=1 AND mode=1)::INT) AS heating_on_rows,sum((state=1 AND mode=2)::INT) AS cooling_on_rows
 FROM read_parquet(?) WHERE quality_admitted AND admitted_room GROUP BY block,room,split ORDER BY block,room,split''',[source])
records=[dict(zip([c[0] for c in cur.description],r)) for r in cur.fetchall()]
dump(out/'room_state_support.json',records)
cal=load(BASE/'runs/BL_TEMPERATURE_02/calibration.json')
ranks={str(rank):sum(r['rank']==rank for r in cal['rooms']) for rank in sorted({r['rank'] for r in cal['rooms']})}
result={'status':'descriptive_support_only_no_model_change','rank_distribution':ranks,
 'training_rank_below6_rooms':sum(r['rank']<6 for r in cal['rooms']),
 'interpretation':'25/36rooms lack full six-column training rank. This limits coefficient identification; not proof of a single causal explanation for heldout degradation. No rooms removed, no ridge/fallback or refit after seeing scores.',
 'test_on_rows':58528,'test_total':548660,'test_on_share':58528/548660,
 'outputs':{'room_state_support.json':sha(out/'room_state_support.json')},'script_sha256':sha(Path(__file__))}
dump(out/'summary.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
