"""Freeze the component validation before any outdoor model errors, no fitting."""
from pathlib import Path
import hashlib
import json
from datetime import datetime,timezone

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    qa=BASE/'runs/IEA_SOURCE_QA_01'
    manifest=json.loads((qa/'source_manifest.json').read_text())
    for item in manifest:assert sha(ROOT/item['path'])==item['sha256']
    par=json.loads((qa/'lab_parameters.json').read_text())
    protocol={
        'id':'IEA_COMPONENT_DC_V1','decision':'D052','date':'2026-10-15',
        'frozen_utc':datetime.now(timezone.utc).isoformat(),
        'object':'Publisher anonymous mono-crystalline silicon module, SUPSI PVLab lab matrix and outdoor I-V observations, 2018-07 through 2019-06. Not PVDAQ1239 or Sharp module.',
        'question':'Does fixed lab temperature correction improve same-label measured module DC maximum power reconstruction over fixed irradiance-only STC scaling?',
        'sources':manifest,'lab_parameters':par,
        'parameter_protocol':'P0 from workbook C10=285.68591743441357 W at1000 W/m2,25 C; gamma from K9=-0.405 percent/C divided100. No outdoor scale, gamma, loss, time shift or any hyperparameter fitted.',
        'time':'Use published Date/Time together, no timezone conversion or averaging-window interpretation; five-minute exact labels, no interpolation or filling missing/night rows. Evaluate observed labels only, not complete-year yield.',
        'prior_exposure':'Source quality/ranges and field definitions seen for all12 months, no model errors computed. Parameters fixed from separate lab characterization. Retrospective validation; not blind trial, independent site, or independent module.',
        'reference_quality':'Core Pm,Voc,Isc,Tbom,Gpoa all finite. Main cohort additionally Pm>=0,Voc>0,Isc>0,Pm<=Voc*Isc+0.001 W, G>=0, exact5min. The IV inequality is a necessary same-curve consistency rule; not a sensor-certification test. All raw rows retained; no nameplate/residual/outlier trimming. Also report all finite core with G>=0 as explicitly reference-flagged sensitivity.',
        'models':{
            'B_G':'P0*Gpoa/1000; lab-rated irradiance-only baseline; no outdoor calibration.',
            'M_T0':'P0*Gpoa/1000*(1+gamma*(Tbom-25)); primary fixed-lab temperature model with back-temperature proxy.',
            'M_T3':'P0*Gpoa/1000*(1+gamma*(Tbom+3*Gpoa/1000-25)); secondary fixed cell-back gradient sensitivity only, never selected as best model.'},
        'temperature_limit':'Tbom is module-back surface, not measured cell temperature. DeltaT=0 main approximation and DeltaT=3 C per1000W/m2 transferred SAPM representative open-rack glass/polymer assumption; actual outdoor mounting/gradient not independently known. No claim either is true Tcell.',
        'irradiance_limit':'Total POA as effective irradiance approximation, no independent spectral/AOI/soiling correction; no solar geometry inferred from unknown timezone.',
        'metrics':{'primary':['MAE_W','RMSE_W'],'secondary':['bias_W','nearest_rank_p95_W','max_abs_W_and_time','monthly_all12','G_lt200','G_ge200','outside_lab_matrix_range_count'],
                   'all_core_sensitivity':'Report scores including IV-inconsistent source rows, never use sensitivity to choose model or hide cohort differences.',
                   'normalisation':'Errors divided by lab P0 diagnostic only; not accuracy or 103 ninety percent. No MAPE near zero and no energy integration.'},
        'criterion':'M_T0 positive component evidence only if both primary MAE and RMSE improve on the same main cohort over B_G. Report every month and worst point even if overall improves. No absolute business-use accuracy threshold, no automatic full PV resource acceptance.',
        'failure':'Any nonpositive temperature factor or nonfinite prediction is a model failure, not silently dropped or clipped. No automatic model tuning or point rejection after errors.',
        'stop':'One evaluation, deterministic replay and independent raw-source/parameter/metric verification. Candidate success/failure with fixed scope. PVDAQ AC failure retained. Final whole-resource acceptance separately checks remaining object/control/forecast evidence.',
        'license':'Annex1 says open-source data for modeling comparison, public download. No specific CC/SPDX raw redistribution license found; local analysis/aggregate evidence, no raw redistribution or relicense.',
        'not_validated':['distributed system AC output','future forecast','maximum available AC power','curtailment/upward reserve','response delay','independent module/site transfer','annual yield','103 official accuracy']
    }
    path=BASE/'iea_component_protocol_v1.json'
    with path.open('x',encoding='utf-8') as f:json.dump(protocol,f,ensure_ascii=False,indent=2);f.write('\n')
    receipt={'protocol_sha256':sha(path),'freeze_script_sha256':sha(Path(__file__)),'state':'frozen_before_model_errors','lab_parameters_sha256':sha(qa/'lab_parameters.json')}
    with (BASE/'iea_component_freeze_receipt_v1.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2)
    print(json.dumps(receipt))

if __name__=='__main__':main()
