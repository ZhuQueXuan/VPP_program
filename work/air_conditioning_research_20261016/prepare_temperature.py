"""Build original-adjacent temperature samples under the frozen protocol."""
from common import *
import sys
sys.path.insert(0,str(ROOT/'work/python_packages/pv_metadata_20261015'))
import duckdb
out=BASE/'runs/PREP_TEMPERATURE_01';out.mkdir(parents=True,exist_ok=False)
pp=BASE/'temperature_protocol_v1.json';p=load(pp);assert sha(pp)==load(BASE/'temperature_freeze_v1.json')['protocol_sha256']
for s in p['sources'].values():assert sha(ROOT/s['path'])==s['sha256']
con=duckdb.connect(str(BASE/'runs/PLEIA_SOURCE_QA_01/quality.duckdb'),read_only=True)
con.execute("SET memory_limit='768MB'");con.execute('SET threads=2');con.execute("SET TimeZone='UTC'")
def rows(sql):
    cur=con.execute(sql);return [dict(zip([c[0] for c in cur.description],r)) for r in cur.fetchall()]
con.execute('''CREATE TEMP TABLE roommap AS WITH s AS(SELECT block,room,min(id) AS sid,count(*) AS n FROM sensor_relation GROUP BY block,room),
 h AS(SELECT block,room,min(id) AS hid,count(*) AS n FROM hvac_relation GROUP BY block,room)
 SELECT s.block,s.room,s.sid,h.hid FROM s JOIN h USING(block,room) WHERE s.n=1 AND h.n=1
 AND h.hid NOT IN(SELECT id FROM hvac_relation GROUP BY id HAVING count(*)>1)''')
con.execute('''CREATE TEMP TABLE sensor_ordered AS WITH d AS(SELECT s.*,r.block,r.room,r.hid,count(*) OVER(PARTITION BY s.id,s.t) AS nt
 FROM sensor s JOIN roommap r ON s.id=r.sid)
 SELECT *,lag(temp) OVER w AS prev_temp,lead(temp) OVER w AS target_temp,
 lag(t) OVER w AS prev_t,lead(t) OVER w AS target_t,lag(nt) OVER w AS prev_nt,lead(nt) OVER w AS target_nt
 FROM d WINDOW w AS(PARTITION BY id ORDER BY srcrow DESC)''')
con.execute('''CREATE TEMP TABLE hvac_keys AS SELECT id,t,count(*) AS key_count,min(state) AS state,min(mode) AS mode,min(setpoint) AS setpoint
 FROM hvac WHERE id IN(SELECT hid FROM roommap) GROUP BY id,t''')
con.execute('''CREATE TEMP TABLE candidates AS WITH j AS(SELECT s.block,s.room,s.id AS sensor_id,s.hid AS hvac_id,s.srcrow,
 epoch_ms(s.prev_t) AS prev_ms,epoch_ms(s.t) AS origin_ms,epoch_ms(s.target_t) AS target_ms,
 s.prev_temp,s.temp,s.target_temp,s.nt,s.prev_nt,s.target_nt,
 epoch_ms(h.t) AS hvac_ms,h.key_count,h.state,h.mode,h.setpoint
 FROM sensor_ordered s ASOF LEFT JOIN hvac_keys h ON s.hid=h.id AND s.t>=h.t)
 SELECT *,
 (prev_ms IS NULL OR target_ms IS NULL) AS window_missing,
 (nt<>1 OR coalesce(prev_nt,0)<>1 OR coalesce(target_nt,0)<>1) AS sensor_time_ambiguous,
 (coalesce(origin_ms-prev_ms,0) NOT BETWEEN 540000 AND 660000 OR coalesce(target_ms-origin_ms,0) NOT BETWEEN 540000 AND 660000) AS cadence_invalid,
 (NOT coalesce(isfinite(temp) AND isfinite(prev_temp) AND isfinite(target_temp) AND temp BETWEEN 0 AND 60 AND prev_temp BETWEEN 0 AND 60 AND target_temp BETWEEN 0 AND 60,false)) AS temperature_invalid,
 (hvac_ms IS NULL OR origin_ms-hvac_ms NOT BETWEEN 0 AND 600000) AS control_unavailable_or_stale,
 (coalesce(key_count,0)<>1) AS control_time_ambiguous,
 (NOT coalesce(state IN(0,1) AND mode IN(0,1,2) AND (state=0 OR mode IN(1,2)) AND isfinite(setpoint) AND setpoint BETWEEN 5 AND 40,false)) AS control_fields_outside_study,
 CASE WHEN origin_ms>=1609459200000 AND target_ms<1630454400000 THEN 'training'
 WHEN origin_ms>=1630454400000 AND target_ms<1640995200000 THEN 'test' ELSE 'outside_split' END AS split
 FROM j''')
flags=['window_missing','sensor_time_ambiguous','cadence_invalid','temperature_invalid','control_unavailable_or_stale','control_time_ambiguous','control_fields_outside_study']
where=' AND '.join('NOT '+f for f in flags)+" AND split<>'outside_split'"
con.execute('CREATE TEMP TABLE marked AS SELECT *,('+where+') AS quality_admitted FROM candidates')
room_rows=rows('''SELECT block,room,sensor_id,hvac_id,count(*) AS candidates,
 sum((quality_admitted AND split='training')::INT) AS train_rows,
 sum((quality_admitted AND split='test')::INT) AS test_rows FROM marked GROUP BY ALL ORDER BY block,room''')
for r in room_rows:r['admitted_room']=r['train_rows']>=1000 and r['test_rows']>=1000
dump(out/'room_coverage.json',room_rows)
allowed={(r['block'],r['room']) for r in room_rows if r['admitted_room']}
assert allowed,'No rooms met prespecified coverage, stop before fit.'
con.execute('CREATE TEMP TABLE room_admission(block VARCHAR,room VARCHAR)')
con.executemany('INSERT INTO room_admission VALUES(?,?)',sorted(allowed))
dest=str(out/'all_candidates.parquet').replace('\\','/').replace("'","''")
con.execute("COPY(SELECT m.*,r.room IS NOT NULL AS admitted_room FROM marked m LEFT JOIN room_admission r USING(block,room) ORDER BY block,room,srcrow DESC) TO '"+dest+"' (FORMAT PARQUET,COMPRESSION ZSTD)")
summary={'date':'2026-10-16','protocol_sha256':sha(pp),'candidate_rooms':len(room_rows),'admitted_rooms':len(allowed),
 'candidate_sensor_rows':rows('SELECT count(*) AS n FROM marked')[0]['n'],
 'exclusion_flags_overlapping':{f:rows('SELECT sum('+f+'::INT) AS n FROM marked')[0]['n'] for f in flags},
 'outside_split':rows("SELECT count(*) AS n FROM marked WHERE split='outside_split'")[0]['n'],
 'admitted_training':sum(r['train_rows'] for r in room_rows if r['admitted_room']),
 'admitted_test':sum(r['test_rows'] for r in room_rows if r['admitted_room']),
 'model_errors_not_yet_computed':True,'notes':'All original adjacent observations retained with flags; author processed files, weather and electricity not used.'}
dump(out/'summary.json',summary);con.close()
dump(out/'admission.json',{'status':'samples_frozen_before_fit','protocol_sha256':sha(pp),'script_sha256':sha(Path(__file__)),
 'outputs':{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
print(json.dumps(summary,ensure_ascii=False,indent=2))
