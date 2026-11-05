"""Current B1/B2/B3 stable research entry. No public trial-index selection."""
from b1_adapter import extract_event,fit_factor,predict_factor,learn_graph
from b2_adapter import predict_single,predict_remaining
from controller import assess_arrival
from legacy_guard import query_previous
from loaders import isolated
from contracts import failed
def assess_single_joint(case,dependence='independent'):
    try:
        with isolated('bridge') as old:return old.assess_joint(case,dependence=dependence,include_traces=False)
    except (ValueError,TypeError,KeyError,IndexError,OverflowError) as e:return failed(e)
__all__=['extract_event','fit_factor','predict_factor','learn_graph','predict_single','predict_remaining','assess_arrival','query_previous','assess_single_joint']
