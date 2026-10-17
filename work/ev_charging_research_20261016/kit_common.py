"""Independent KIT current-response research; no cross-source entity joining."""
from mapping_common import *
import sys
sys.path.insert(0,str(ROOT/'work/python_packages/pv_metadata_20261015'))
import duckdb
import numpy as np
SOURCE=BASE/'downloads/KIT_LF_SOURCE_01'
def connection():
    con=duckdb.connect();con.execute("SET memory_limit='768MB'");con.execute('SET threads=2')
    return con
def trace(con,uid):
    return con.execute('SELECT file_row_number,epoch_us(timestamp_ns) AS t_us,cast(i_l1_a as double) AS i1,cast(i_l2_a as double) AS i2,cast(i_l3_a as double) AS i3,setpoint_a AS u FROM read_parquet(?,file_row_number=true) WHERE charging_uuid=cast(? as UUID) ORDER BY file_row_number',[str(SOURCE/'ev-charging_lf.parquet'),uid]).fetchnumpy()
