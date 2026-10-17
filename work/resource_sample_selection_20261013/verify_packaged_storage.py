"""Packaging regression checks. Process code intentionally stays outside release."""
import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path(__file__).resolve().parent
RELEASE=ROOT/'resource_research_results/lithium_ion_storage'
CODE=RELEASE/'code'
WORK=SOURCE/'downloads/blyth_ecm_20261015/package_verification'
sys.path.insert(0,str(ROOT/'work/teacher_storage_brief_20261014/plot_dependencies'))
sys.path.insert(0,str(ROOT/'work/python_packages/storage_ecm_20261015'))
sys.path.insert(0,str(CODE))

def load(name):
    spec=importlib.util.spec_from_file_location('released_'+name,CODE/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--part',choices=['conversion_power','voltage'],required=True)
    args=parser.parse_args()
    WORK.mkdir(exist_ok=True)
    out=WORK/(args.part+'.json');assert not out.exists()
    started=time.perf_counter()
    result={'part':args.part,'status':'passed'}
    if args.part=='conversion_power':
        conversion=load('conversion')
        parameters=json.loads((RELEASE/'parameters/conversion_m5bat.json').read_text(encoding='utf-8'))
        difference=0.;count=0
        with (SOURCE/'baseline_runs/BL_M5BAT_20261013_01/predictions.csv').open(newline='',encoding='utf-8') as f:
            for row in csv.DictReader(f):
                prediction=conversion.predict(row['unit_id'],row['direction'],float(row['ac_mean_kw']),True,parameters)
                difference=max(difference,abs(prediction['dc_predicted_kw']-float(row['b1_dc_hat_kw'])))
                count+=1
        assert count==2911 and difference<1e-8
        assert conversion.predict('unknown','charge',-300,True,parameters)['dc_predicted_kw'] is None
        assert conversion.predict('lmo1','charge',-300,False,parameters)['dc_predicted_kw'] is None
        assert conversion.predict('lmo1','charge',300,True,parameters)['dc_predicted_kw'] is None
        assert conversion.predict('lmo1','charge',-1000,True,parameters)['outside_fit_power_support']
        result['conversion']={'rows':count,'max_difference_kw':difference,'domain_guards_passed':True}
        power=load('log_power_forecast')
        beta=json.loads((RELEASE/'parameters/log_power_lmo1.json').read_text())['beta']
        x_path=SOURCE/'apr2023_response_sample_runs/PREP_APR_RESPONSE_20261013_01/inputs.csv.gz'
        y_path=SOURCE/'apr2023_response_baseline_runs/BL_APR_RESPONSE_20261013_01/predictions.csv.gz'
        n=0;maxdiff=0.
        with gzip.open(x_path,'rt',newline='',encoding='utf-8') as xf,gzip.open(y_path,'rt',newline='',encoding='utf-8') as yf:
            xreader=csv.DictReader(xf);yreader=csv.DictReader(yf)
            for row,expected in zip(xreader,yreader,strict=True):
                assert row['sample_id']==expected['sample_id']
                mode=next((name for flag,name in [('mode_pq_t','PQ'),('mode_stop_t','Stop'),('mode_silent_t','Silent'),('mode_wait_t','Wait')]
                           if float(row[flag])==1),'unknown')
                pred=power.predict(float(row['ac_t_kw']),float(row['set_t_kw']),mode,beta)
                for key,target in [('persistence_kw','B0_predicted_kw'),('setpoint_baseline_kw','B_SET_predicted_kw'),('blend_kw','B1_predicted_kw')]:
                    maxdiff=max(maxdiff,abs(pred[key]-float(expected[target])))
                n+=1
        assert n==2591994 and maxdiff<1e-10
        result['log_power']={'rows':n,'models':3,'max_difference_kw':maxdiff}
    else:
        import numpy as np
        import pandas as pd
        voltage=load('voltage_model')
        raw=pd.read_csv(SOURCE/'downloads/blyth_ecm_20261015/wltp_source_rows.csv')
        values=voltage.simulate(raw.time_s.to_numpy(),raw.current_discharge_A.to_numpy())
        expected=pd.read_csv(SOURCE/'downloads/blyth_ecm_20261015/BL_BLYTH_VOLTAGE_20261015_01/predictions.csv')
        maxdiff=0.
        for key,reference in [('voltage_2rc_V','B_2RC_voltage_V'),('voltage_r0_V','B_R0_voltage_V'),
                              ('soc_from_given_initial','soc_from_given_initial')]:
            maxdiff=max(maxdiff,float(np.max(np.abs(values[key]-expected[reference].to_numpy()))))
        assert len(values['time_s'])==79058 and maxdiff<1e-10
        for t,i,soc in [([0,1],[0,-1],1),([1,2],[0,0],1),([0,1],[0,0],.01)]:
            try:voltage.simulate(t,i,soc)
            except ValueError:pass
            else:raise AssertionError('Missing input/domain guard')
        result['voltage']={'rows':79058,'max_difference_V_or_SOC':maxdiff,'domain_guards_passed':True,
                            'scope':'same original benchmark replay, not independent field confirmation'}
    result['elapsed_s']=time.perf_counter()-started
    out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':main()
