"""Freeze explicitly post-outcome descriptive checks, not new model validation."""
from common import *
import datetime
p=BASE/'hil_diagnostic_protocol_v1.json';assert not p.exists()
old=load(BASE/'hil_power_protocol_v1.json')
protocol={
 'decision':'D061','frozen_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'status':'Posthoc descriptive protocol, fixed after D060 errors were already seen. Not preregistered blind evidence, not a new success gate.',
 'question':'Are fixed-model electric-power errors concentrated near observed abrupt outdoor-electric-power changes, and what source limitations prevent a command/stage/latency interpretation?',
 'sources':old['sources'],
 'old_protocol_sha256':sha(BASE/'hil_power_protocol_v1.json'),
 'calibration_sha256':sha(BASE/'runs/BL_HIL_POWER_01/calibration.json'),
 'old_predictions_sha256':sha(BASE/'runs/BL_HIL_POWER_01/predictions.csv'),
 'model':'Use unchanged D060 B_COP/M_TEMP coefficients and original same-row target on every row; zero fit/tuning/shift/filter/clipping. Training files shown as descriptive development data only.',
 'proxy':'An observed outdoor-electric-power jump is a row i>0 with abs(Pout[i]-Pout[i-1]) >= 500 W on the source strict 1s clock. This research threshold is chosen post-outcome, not calibrated compressor state or a control command. Include negative power readings.',
 'window':'Mark all rows within inclusive +/-60 seconds of any proxy jump, union overlaps once; clip at file boundaries and count clipped windows. Complement is all remaining rows, NOT certified steady state. All rows remain in pooled original score.',
 'groups':['all','within_60s_of_observed_jump','other_rows','Q_le0_and_Ptotal_ge1000W'],
 'statistics':'Counts, MAE/RMSE, sum of absolute errors and sum of squared errors for fixed B_COP/M_TEMP; row and error contribution shares. No group-specific gain as acceptance or deployment route.',
 'context':'Export original source rows +/-180 seconds of the previously reported M_TEMP worst point, file85F row673. This is a deliberately chosen worst-case illustration, not random or representative evidence.',
 'causality':'No inferred true compressor on/off/two-stage labels; no command-to-output response delay, lag optimisation, causal synchronisation finding or sensor fault diagnosis.',
 'preserve':'Keep all D059/D060 protocols, predictions, parameters, failures, source data and existing three resource packages unchanged; no final HVAC package.'
}
dump(p,protocol);dump(BASE/'hil_diagnostic_freeze_v1.json',{'protocol_sha256':sha(p),'created_utc':protocol['frozen_utc']})
print(sha(p))
