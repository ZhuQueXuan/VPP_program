"""Public B1 v1 entry. Existing b123_api remains a frozen compatibility interface."""
from b1_algorithm import __version__,provided_reference,analyze_event,analyze_events,estimate_event_effects
from b1_algorithm.reference import (ReferenceWindow,ReferenceTrainingRecord,WindowCalibrationRecord,
    fit_reference,predict_reference,calibrate_window_reference,save_reference_model,load_reference_model)
from b1_algorithm.effects import fit_effects
from b1_algorithm.metered_effects import estimate_metered_effects
from b1_algorithm.resources import EVAnalysisConfig,assess_ev_recovery
from b1_algorithm.api import estimate_event_curve
from b1_algorithm.metered_effects import estimate_metered_curve
from b1_algorithm.effects.continuous import ContinuousEffectConfig,fit_continuous_effects
from b1_algorithm.effects.plotting import export_incentive_curve
from b1_algorithm.factors import (EVFactorStudy,describe_ev_study,fit_ev_factor_curve,screen_incentive_parents,analyze_ev_factor_study)
from b1_algorithm.reference.ev_selection import select_ev_reference
from b1_algorithm.effects.frozen import (FrozenContinuousModel,fit_continuous_model,fit_ev_factor_model,
    save_continuous_model,load_continuous_model,query_continuous_model,find_incentive_threshold)
from b1_algorithm.history import (EVHistoryEncoder,prepare_ev_history,fit_ev_history_encoder,
    encode_ev_history,save_ev_history_encoder,load_ev_history_encoder)
from b1_algorithm.reference.reliable import (FrozenEVReferenceModel,fit_ev_reference_error_model,
    predict_ev_reliable_reference,save_ev_reliable_reference_model,load_ev_reliable_reference_model)
from b1_algorithm.response_evidence import (EVEventCalibration,event_scan_score,fit_ev_event_calibration,
    assess_ev_event_evidence,save_ev_event_calibration,load_ev_event_calibration)
from b1_algorithm.effects.tuning import (TuningSelection,select_continuous_tuning,describe_continuous_tuning,
    save_continuous_tuning,load_continuous_tuning,fit_tuned_continuous_effects,fit_tuned_continuous_model)

__all__=['__version__','provided_reference','analyze_event','analyze_events','estimate_event_effects',
 'ReferenceWindow','ReferenceTrainingRecord','WindowCalibrationRecord','fit_reference',
 'predict_reference','calibrate_window_reference','save_reference_model','load_reference_model','fit_effects',
 'estimate_metered_effects','EVAnalysisConfig','assess_ev_recovery','estimate_event_curve','estimate_metered_curve',
 'ContinuousEffectConfig','fit_continuous_effects','export_incentive_curve','EVFactorStudy','describe_ev_study',
 'fit_ev_factor_curve','screen_incentive_parents','analyze_ev_factor_study','select_ev_reference',
 'FrozenContinuousModel','fit_continuous_model','fit_ev_factor_model','save_continuous_model',
 'load_continuous_model','query_continuous_model','find_incentive_threshold',
 'EVHistoryEncoder','prepare_ev_history','fit_ev_history_encoder','encode_ev_history',
 'save_ev_history_encoder','load_ev_history_encoder',
 'FrozenEVReferenceModel','fit_ev_reference_error_model','predict_ev_reliable_reference',
 'save_ev_reliable_reference_model','load_ev_reliable_reference_model',
 'EVEventCalibration','event_scan_score','fit_ev_event_calibration','assess_ev_event_evidence',
 'save_ev_event_calibration','load_ev_event_calibration',
 'TuningSelection','select_continuous_tuning','describe_continuous_tuning','save_continuous_tuning',
 'load_continuous_tuning','fit_tuned_continuous_effects','fit_tuned_continuous_model']
