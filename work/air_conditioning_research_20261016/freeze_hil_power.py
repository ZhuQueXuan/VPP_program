"""Freeze independent-source static electric-power reconstruction before fit."""
from common import *
from datetime import datetime,timezone
src=BASE/'downloads/HIL_AC_SOURCE_01';out=BASE/'hil_power_protocol_v1.json';assert not out.exists()
files=[r for r in load(src/'receipt.json')['files'] if r['name'].startswith('AC_')]
protocol={'date':'2026-10-16','decision':'D060','frozen_utc':datetime.now(timezone.utc).isoformat(),
 'question':'Does a temperature-dependent inverse-COP statistical mapping improve same-record indoor+outdoor electric power reconstruction over a constant-slope mapping on two held-out ambient-condition experiments?',
 'object':'One two-stage SEER21 2-ton central AC cooling device, five whole laboratory/HIL tests. Not field-room behaviour, not five independent devices. Different object from PLEIA.',
 'sources':{r['name']:{'path':(src/r['name']).relative_to(ROOT).as_posix(),'sha256':r['sha256']} for r in files},
 'documents':{p.name:{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)} for p in [src/'Test_Matrix.xlsx',src/'hil_validation.pdf',BASE/'downloads/MATCHED_SOURCE_01/hil_catalog.html',BASE/'downloads/MATCHED_SOURCE_01/hil_license.html',BASE/'runs/HIL_AC_QA_01/summary.json']},
 'input':'Same published row source-calculated air-side Cooling Capacity(kW) and measured T_Outdoor(C). No electric power, thermostat, future record, virtual room state or control-inferred-from-target as model inputs.',
 'reference':'Same row measured Outdoor Unit Power(W)+Indoor Unit Power(W). Sum is target only, never a predictor. Q is thermal, not electrical kW; source-calculated from air-side measurements, not independent calorimeter truth.',
 'sample':'Every original row of all5explicit AC files; preserve original row order. Inputs and both reference powers finite. Naive clocks must parse and be strictly1s adjacent per file; reject any affected current row and flag without reordering/filling. First row may enter static mapping if finite/parseable. No threshold on Q/P/sign/residual/steady/transient/thermostat state; negative published values retained.',
 'split':{'training_OAT_F':[75,95,115],'test_OAT_F':[85,105],
  'method':'Prespecified alternating design-temperature whole-file interpolation split: span low/middle/high in training and evaluate interior conditions. Not chronological forecasting: some training experiments occur after test experiments. No same-test adjacent-row random split, no claims of future time/site/device generalisation.'},
 'models':{'B_MEAN':'Each training experiment equal weight mean electric power, diagnostic only',
  'B_COP':'beta0+beta1*Q_kW,2fitted parameters, constant inverse-COP slope plus fixed power intercept',
  'M_TEMP':'beta0+beta1*Q_kW+beta2*Q_kW*(T_Outdoor_C-35),3fitted parameters; first-order inverse-COP ambient correction motivated by cooling efficiency dependence on conditions',
  'fit':'OLS rcond1e-12 with each training file equal total weight. No regularisation/clipping/physical coefficient constraints/parameter search/selection on test errors. Intercept and slopes statistical, not manufacturer COP/guaranteed upper bound. SEER21 is not an instantaneous COP21.'},
 'success':'M_TEMP versus B_COP pooled and each of2testfiles MAE/RMSE strictly lower, and pooled source-Q>=1kW subset both lower. Q>=1 is predeclared input-based diagnostic group, not training/admission filter. B_MEAN diagnostic only, not swapped to make success.',
 'report':['all rows/quality and sign counts','both complete test experiments and equal-file means','Q>=1 and Q<1 groups','all training rank/coefficients/ranges','outside training Q/T ranges flagged but retained','worst errors, negative estimates, no fitted clipping','deterministic replay and independent raw parser/algebra verification'],
 'not_verified':['future online forecasting','command-to-power timing','physical capacity/firm curtailment/field-room comfort','generalisation beyond same hardware HIL conditions','causal COP/heat-parameter identification','P1/103formal90percent'],
 'no_old_holdout_tuning':'PLEIA failed ARX unchanged; no transfer of those coefficients or already-seen test residuals.'}
dump(out,protocol);dump(BASE/'hil_power_freeze_v1.json',{'date':'2026-10-16','protocol_sha256':sha(out),'before_fit_errors':True,'script_sha256':sha(Path(__file__))})
print(sha(out))
