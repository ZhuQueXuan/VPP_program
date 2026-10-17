"""Full original-field/time/entity QA. No predictions or outcome-based filtering."""
from common import *
import zipfile,shutil,sys
sys.path.insert(0,str(ROOT/'work/python_packages/pv_metadata_20261015'))
import duckdb

out=BASE/'runs/PLEIA_SOURCE_QA_01';out.mkdir(parents=True,exist_ok=False)
source=BASE/'downloads/PLEIA_RAW_01';archive=source/'Data_Nature.zip'
assert sha(archive)==load(source/'receipt.json')['files'][0]['sha256']
raw=source/'selected_raw';raw.mkdir(exist_ok=False)
names=['data-cons.csv','data-hvac.csv','data-sensor.csv','MU62_dm.txt','relations-hvac.csv','relations-sensor.csv']
with zipfile.ZipFile(archive) as z:
    for name in names:
        with z.open('Data_Nature/raw_data/'+name) as fi,(raw/name).open('xb') as fo:shutil.copyfileobj(fi,fo)
con=duckdb.connect(str(out/'quality.duckdb'));con.execute("SET memory_limit='768MB'");con.execute('SET threads=2');con.execute("SET TimeZone='UTC'")
def rows(sql,args=None):
    cursor=con.execute(sql,args or []);return [dict(zip([c[0] for c in cursor.description],r)) for r in cursor.fetchall()]
def readexpr(name):return "read_csv('"+str(raw/name).replace('\\','/').replace("'","''")+"',delim=';',header=true,all_varchar=true,parallel=false)"
for table,file,numbers in [('sensor','data-sensor.csv',{'V2':'temp'}),('hvac','data-hvac.csv',{'V4':'state','V5':'mode','V6':'v6','V12':'setpoint','V26':'v26'}),('meter','data-cons.csv',{'V22':'energy'})]:
    fields=', '.join('try_cast('+k+' AS DOUBLE) AS '+v for k,v in numbers.items())
    con.execute('CREATE TABLE '+table+' AS SELECT row_number() OVER () AS srcrow,try_cast(IDdevice AS BIGINT) AS id,Date AS time_text,try_cast(Date AS TIMESTAMPTZ) AS t,'+fields+' FROM '+readexpr(file))
    sql='SELECT count(*) AS rows,count(DISTINCT id) AS devices,sum((t IS NULL)::INT) AS unparsed_times,min(t)::VARCHAR AS first_time_UTC,max(t)::VARCHAR AS last_time_UTC FROM '+table
    info=rows(sql)[0]
    info['per_device']=rows('''WITH d AS (SELECT *,epoch_ms(t)-lag(epoch_ms(t)) OVER(PARTITION BY id ORDER BY srcrow) AS original_dt FROM '''+table+''')
      SELECT id,count(*) AS rows,min(t)::VARCHAR AS first_UTC,max(t)::VARCHAR AS last_UTC,
      sum((original_dt>0)::INT) AS original_time_increases,sum((original_dt<0)::INT) AS original_time_decreases,
      sum((original_dt=0)::INT) AS adjacent_duplicate_time,count(*)-count(DISTINCT t) AS duplicate_timestamps,
      median(abs(original_dt)) AS median_original_abs_step_ms,max(abs(original_dt)) AS max_original_abs_step_ms
      FROM d GROUP BY id ORDER BY id''')
    info['numeric_fields']={v:rows('SELECT sum(('+v+' IS NULL OR NOT isfinite('+v+'))::INT) AS nonfinite,min('+v+') AS minimum,max('+v+') AS maximum FROM '+table)[0] for v in numbers.values()}
    info['offset_suffixes']=rows("SELECT regexp_extract(time_text,'([+-][0-9]{2}(:[0-9]{2})?)$',1) AS offset_suffix,count(*) AS n FROM "+table+' GROUP BY 1 ORDER BY 1')
    if table=='hvac':
        info['enums']={v:rows('SELECT '+v+' AS value,count(*) AS n FROM hvac GROUP BY 1 ORDER BY 1') for v in ('state','mode','v6','v26')}
        info['by_month']=rows("SELECT strftime(t,'%Y-%m') AS month,count(*) AS n,sum((state=1)::INT) AS on_rows,sum((mode=2 AND state=1)::INT) AS on_cooling_rows FROM hvac GROUP BY 1 ORDER BY 1")
    if table=='sensor':info['plausibility_flags_only']=rows('SELECT sum((temp<0 OR temp>60)::INT) AS outside_author_screen_0_60_C FROM sensor')[0]
    if table=='meter':
        info['chronological_differences']=rows('''WITH d AS (SELECT *,energy-lag(energy) OVER(PARTITION BY id ORDER BY t,srcrow) AS delta FROM meter)
          SELECT id,count(*) AS rows,sum((delta<0)::INT) AS negative_differences,sum((delta=0)::INT) AS zero_differences,min(delta) AS minimum_delta_kWh,max(delta) AS maximum_delta_kWh FROM d GROUP BY id ORDER BY id''')
    dump(out/(table+'_quality.json'),info)
    print(table,json.dumps({k:v for k,v in info.items() if k not in ('per_device','enums','offset_suffixes','by_month')},ensure_ascii=False),flush=True)

for table,file in [('sensor_relation','relations-sensor.csv'),('hvac_relation','relations-hvac.csv')]:
    con.execute('CREATE TABLE '+table+' AS SELECT cast(ID AS BIGINT) AS id,block,room FROM '+readexpr(file))
relations={table:rows('SELECT * FROM '+table+' ORDER BY block,room,id') for table in ('sensor_relation','hvac_relation')}
relations['relation_summary']={r:rows('SELECT count(*) AS rows,count(DISTINCT id) AS ids,count(DISTINCT(block,room)) AS rooms FROM '+r)[0] for r in ('sensor_relation','hvac_relation')}
relations['mapping_conflicts']={r:rows('SELECT id,count(*) AS rows,count(DISTINCT(block,room)) AS rooms FROM '+r+' GROUP BY id HAVING count(*)>1') for r in ('sensor_relation','hvac_relation')}
relations['unmapped_recorded_ids']={r:rows('SELECT DISTINCT a.id FROM '+table+' a ANTI JOIN '+r+' b USING(id) ORDER BY a.id') for table,r in [('sensor','sensor_relation'),('hvac','hvac_relation')]}
relations['relation_ids_without_records']={r:rows('SELECT DISTINCT a.id FROM '+r+' a ANTI JOIN '+table+' b USING(id) ORDER BY a.id') for table,r in [('sensor','sensor_relation'),('hvac','hvac_relation')]}
relations['room_cardinality']=rows('''WITH s AS(SELECT block,room,count(DISTINCT id) AS sensors FROM sensor_relation GROUP BY block,room),
 h AS(SELECT block,room,count(DISTINCT id) AS hvacs FROM hvac_relation GROUP BY block,room)
 SELECT coalesce(s.block,h.block) AS block,coalesce(s.room,h.room) AS room,sensors,hvacs FROM s FULL JOIN h USING(block,room) ORDER BY 1,2''')
relations['single_sensor_single_hvac_rooms']=[r for r in relations['room_cardinality'] if r['sensors']==1 and r['hvacs']==1]
dump(out/'relations_quality.json',relations)
con.execute('CREATE TABLE weather AS SELECT * FROM '+readexpr('MU62_dm.txt'))
weather={'rows':rows('SELECT count(*) AS n FROM weather')[0]['n'],'columns':rows('DESCRIBE weather'),
 'limits':'Raw fecha/hora lack explicit UTC offset; do not align to building offset times by assuming timezone or current availability. Not admitted as forecast predictor.'}
dump(out/'weather_quality.json',weather)
con.close()
summary={'date':'2026-10-16','source_record':7620136,'license':'CC-BY-4.0 per retrieved original metadata',
 'archive_bytes':archive.stat().st_size,'archive_sha256':sha(archive),'archive_MD5':'3a65b744ce960c0bced4285c7cc6d3d4',
 'raw_counts':{t:load(out/(t+'_quality.json'))['rows'] for t in ('sensor','hvac','meter')},
 'single_sensor_single_hvac_rooms':len(relations['single_sensor_single_hvac_rooms']),
 'status':'original_source_fields_time_entity_QA_completed; no model/sample admission or fitting yet',
 'issues':['Block cumulative kWh is not single-terminal kW.','Raw building timestamps include explicit offsets; actual recording order and duplicates retained in QA.',
  'Raw records end2021-12-31, unlike paper description end2021-12-18.','Unknown HVAC V6/mode4/type0 not interpreted without dictionary.',
  'Weather timezone/availability unconfirmed.','Author processed room tables may repeat block energy; not used as independent device power.']}
dump(out/'summary.json',summary)
dump(out/'receipt.json',{'status':'completed','script_sha256':sha(Path(__file__)),'duckdb_version':duckdb.__version__,
 'source_files':{p.name:sha(p) for p in sorted(raw.iterdir())},
 'outputs':{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.suffix=='.json'}})
print(json.dumps(summary,ensure_ascii=False,indent=2))
