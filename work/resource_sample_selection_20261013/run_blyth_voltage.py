"""Run a frozen, restricted voltage benchmark using pinned author model code."""
from pathlib import Path
import argparse
import datetime
import hashlib
import importlib.util
import json
import platform
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'work/teacher_storage_brief_20261014/plot_dependencies'))
sys.path.insert(0, str(ROOT / 'work/python_packages/storage_ecm_20261015'))
import numpy as np
import pandas as pd
import scipy

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-id', required=True)
    args = ap.parse_args()
    base = ROOT / 'work/resource_sample_selection_20261013/downloads/blyth_ecm_20261015'
    protocol_path = Path(__file__).with_name('blyth_voltage_protocol_v1.json')
    protocol = json.loads(protocol_path.read_text(encoding='utf-8'))
    out = base / args.run_id
    out.mkdir(exist_ok=False)
    receipt = {'run_id': args.run_id, 'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'protocol_sha256': digest(protocol_path), 'code_sha256': digest(Path(__file__)),
               'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__,
               'scipy': scipy.__version__, 'status': 'running'}
    started = time.perf_counter()
    try:
        for relative, expected in protocol['input_sha256'].items():
            assert digest(base / relative) == expected, relative
        df = pd.read_csv(base / 'wltp_source_rows.csv')
        t = df.time_s.to_numpy(dtype=float)
        current = df.current_discharge_A.to_numpy(dtype=float)
        assert len(t) == protocol['data']['raw_rows'] and np.all(np.diff(t) >= 0)
        def currentfunc(time_s):
            return np.interp(time_s, t, current, 0)
        spec = importlib.util.spec_from_file_location('pinned_author_model', base / 'author/research/scripts/model.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Author model does not expose solve_ivp status; record it without modifying model code.
        original_solver = module.scipy.integrate.solve_ivp
        solver_records = []
        def checked_solver(*a, **kw):
            result = original_solver(*a, **kw)
            solver_records.append({'success': bool(result.success), 'status': result.status,
                                   'message': result.message, 'nfev': result.nfev,
                                   'last_t': float(result.t[-1]), 'output_points': len(result.t)})
            if not result.success:
                raise RuntimeError(result.message)
            return result
        module.scipy.integrate.solve_ivp = checked_solver
        model = module.TheveninModel(str(base / '25C_MLP001_ocv.csv'),
                                    str(base / '25C_MLP001_params.csv'), 2.132)
        eval_t = np.arange(0, 79058, dtype=float)
        ts, inputs, v2, soc, temp, vrc = model.simulate(
            currentfunc, initial_soc=1.0, temp_inf=25.0, t_max=79057.0,
            max_step=2.0, atol=1e-5, rtol=1e-5, method='RK45', t_eval=eval_t)
        assert np.array_equal(ts, eval_t), 'Incomplete output; do not crop'
        assert np.isfinite(v2).all() and np.isfinite(soc).all()
        assert soc.min() >= 0.05 and soc.max() <= 1.01
        v0 = model._ocv_lut(temp, soc) - inputs * model._r_luts[0](temp, soc)
        ref = df.groupby('time_s', sort=False).last()
        assert np.array_equal(ref.index.to_numpy(), ts)
        measured = ref.voltage_V.to_numpy()
        pred = pd.DataFrame({'time_s': ts, 'current_discharge_A': inputs, 'measured_voltage_V': measured,
                             'B_R0_voltage_V': v0, 'B_2RC_voltage_V': v2, 'soc_from_given_initial': soc,
                             'isothermal_C': temp, 'vrc1_V': vrc[0], 'vrc2_V': vrc[1]})
        pred.to_csv(out / 'predictions.csv', index=False, float_format='%.17g')
        metrics = {}
        for name, voltage in [('B_R0', v0), ('B_2RC', v2)]:
            error = (voltage - measured) * 1000
            worst = int(np.argmax(np.abs(error)))
            metrics[name] = {'mae_mV': float(np.mean(np.abs(error))), 'rmse_mV': float(np.sqrt(np.mean(error**2))),
                             'bias_mV': float(np.mean(error)), 'max_abs_mV': float(np.max(np.abs(error))),
                             'p95_abs_mV': float(np.quantile(np.abs(error), .95)), 'count': len(error),
                             'worst_time_s': float(ts[worst]), 'worst_current_A': float(inputs[worst])}
        metrics['comparison'] = {'mae_reduction_fraction': 1-metrics['B_2RC']['mae_mV']/metrics['B_R0']['mae_mV'],
                                  'rmse_reduction_fraction': 1-metrics['B_2RC']['rmse_mV']/metrics['B_R0']['rmse_mV']}
        (out / 'metrics.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')
        receipt.update(status='completed', solver=solver_records, rows=len(pred), coverage=1.0,
                       soc_range=[float(soc.min()), float(soc.max())], metrics=metrics,
                       outputs={name: digest(out / name) for name in ['predictions.csv', 'metrics.json']})
    except Exception:
        receipt.update(status='failed', traceback=traceback.format_exc())
    receipt['elapsed_s'] = time.perf_counter()-started
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding='utf-8')
    (out / 'protocol_snapshot.json').write_bytes(protocol_path.read_bytes())
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    if receipt['status'] != 'completed':
        raise SystemExit(1)

if __name__ == '__main__':
    main()
