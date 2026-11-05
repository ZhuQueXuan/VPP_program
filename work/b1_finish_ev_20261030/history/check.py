"""Small functional controls, separate from the held-out scientific study."""
from pathlib import Path
import os
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import sys
import copy
import json
from dataclasses import FrozenInstanceError
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'B1算法'))
from b1_algorithm.contracts import provided_reference
from b1_algorithm.history import (prepare_ev_history, fit_ev_history_encoder, encode_ev_history,
    save_ev_history_encoder, load_ev_history_encoder, EVHistoryEncoder)


def synthetic(user, shift=0.):
    current = dict(task_id=f'{user}-current', user_id=user, meter_id=user+'-meter',
                   start_min=10000., end_min=10030., notice_min=9985., request_kw=1.5,
                   task_pre_treatment=True, resource_type='EV')
    records = []
    for index in range(3):
        start = 9000. + index*200
        task = dict(current, task_id=f'{user}-past-{index}', start_min=start,
                    end_min=start+30, notice_min=start-15)
        s = start + np.arange(-15., 45.); e = s+1
        ref = np.full(60, 3.8)
        r = np.zeros(60); r[15:15+10+index] = .8 + .2*shift
        r[45:48] = -.5
        records.append(dict(task=task, starts_min=s.tolist(), ends_min=e.tolist(),
            power_kw=(ref-r).tolist(), noise_sigma_kw=.05,
            reference=provided_reference(task, s, e, ref, available_at_min=start-15),
            observed_available_at_min=float(e[-1]), ev_config=dict(max_charge_kw=7.2)))
    return records, current


def main():
    passed = []
    def check(name, condition):
        if not condition: raise AssertionError(name)
        passed.append(name)
    def rejects(name, call):
        try: call()
        except ValueError: passed.append(name)
        else: raise AssertionError(name+' was not rejected')
    records, current = synthetic('control')
    p = prepare_ev_history(records, current)
    check('legal ready raw90 summary6', p['status']=='ok' and len(p['raw'])==90 and len(p['summary'])==6)
    expected = np.concatenate([(np.asarray(r['reference']['reference_kw'])-np.asarray(r['power_kw']))[15:45]/1.5 for r in records])
    check('raw90 direct independent arithmetic', np.allclose(expected, p['raw'], atol=0, rtol=0))
    check('strict chronology', [r['task_id'] for r in p['provenance']]==[r['task']['task_id'] for r in records])
    check('empty history explicit fallback', prepare_ev_history([], current)['status']=='insufficient_history')
    check('two histories explicit fallback', prepare_ev_history(records[:2], current)['raw'] is None)
    check('unordered input sorted, same vector', prepare_ev_history(records[::-1], current)['raw']==p['raw'])
    mutations = {
        'foreign user': lambda r: r[0]['task'].update(user_id='other'),
        'foreign meter': lambda r: r[0]['task'].update(meter_id='other'),
        'late availability': lambda r: r[0].update(observed_available_at_min=current['notice_min']+1),
        'availability before observation end': lambda r: r[0].update(observed_available_at_min=8990.),
        'missing availability': lambda r: r[0].pop('observed_available_at_min'),
        'boolean availability': lambda r: r[0].update(observed_available_at_min=True),
        'string availability': lambda r: r[0].update(observed_available_at_min='9045'),
        'missing meter sample': lambda r: r[0]['power_kw'].pop(),
        'nonfinite observed power': lambda r: r[0]['power_kw'].__setitem__(18, float('nan')),
        'current event history': lambda r: r[0]['task'].update(task_id=current['task_id']),
        'late reference': lambda r: r[0]['reference'].update(available_at_min=r[0]['task']['notice_min']+1),
        'reference identity mismatch': lambda r: r[0]['reference'].update(task_id='wrong'),
    }
    for name, mutation in mutations.items():
        bad = copy.deepcopy(records); mutation(bad)
        rejects(name, lambda bad=bad: prepare_ev_history(bad, current))
    rejects('duplicate history', lambda: prepare_ev_history(records+[records[-1]], current))
    rejects('late explicit cutoff', lambda: prepare_ev_history(records, current, cutoff_min=9990))
    rejects('insufficient at earlier cutoff not silent filter', lambda: prepare_ev_history(records, current, cutoff_min=9200))
    rejects('current nonEV task', lambda: prepare_ev_history(records, dict(current, resource_type='AC')))
    rejects('unsupported current duration', lambda: prepare_ev_history(records, dict(current, end_min=10037)))
    rejects('wrong required events', lambda: prepare_ev_history(records, current, required_events=2))
    training = [prepare_ev_history(*synthetic('train'+str(i), i/10)) for i in range(12)]
    for method in ('stats6', 'pca6', 'ae6'):
        model = fit_ev_history_encoder(training, method=method, seed=820011)
        before = model.payload_json
        out = encode_ev_history(model, p)
        check(method+' finite six values', len(out['values'])==6 and np.isfinite(out['values']).all())
        check(method+' inference no mutation', before==model.payload_json)
        check(method+' heldout user overlap false', out['training_user_overlap'] is False)
        path = HERE / ('check_'+method+'_model.json')
        save_ev_history_encoder(model, path)
        loaded = load_ev_history_encoder(path)
        check(method+' save load exact', loaded==model and encode_ev_history(loaded,p)==out)
        bad = copy.deepcopy(p);bad['raw'][0]+=1
        rejects(method+' modified prepared checksum', lambda: encode_ev_history(model,bad))
        rejects(method+' insufficient cannot encode', lambda: encode_ev_history(model,prepare_ev_history([],current)))
        rejects(method+' altered model checksum', lambda: encode_ev_history(EVHistoryEncoder(model.payload_json,'0'*64),p))
        try: model.payload_json='changed'
        except FrozenInstanceError: passed.append(method+' immutable model')
        else: raise AssertionError('mutable model')
        state=json.loads(model.payload_json)
        if method=='ae6':
            check('fixed60 epochs4752 parameters',state['epochs']==60 and state['parameters']==4752)
            z=(np.asarray(p['raw'])-state['mean'])/state['scale']
            for i in range(2): z=np.tanh(z@np.asarray(state['coefs'][i])+state['intercepts'][i])
            check('AE latent manual exact',np.array_equal(z,np.asarray(out['values'])))
        if method=='pca6':
            z=(np.asarray(p['raw'])-state['mean'])/state['scale']
            check('PCA projection independent arithmetic',np.allclose((z-state['pca_center'])@np.asarray(state['components']).T,out['values'],atol=1e-14))
    rejects('duplicate training tasks',lambda:fit_ev_history_encoder(training+[training[0]]))
    rejects('bool random seed',lambda:fit_ev_history_encoder(training,seed=True))
    receipt=dict(status='passed',checks=len(passed),names=passed,
                 scientific_study_run=False,performance_claim=False)
    (HERE/'check_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(status='passed',checks=len(passed))))


if __name__=='__main__':main()
