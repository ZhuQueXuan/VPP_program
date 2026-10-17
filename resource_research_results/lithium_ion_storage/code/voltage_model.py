"""Pinned author 2RC conditional voltage model with explicit input/domain checks."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from scipy.integrate import solve_ivp
from third_party.thevenin_model import TheveninModel

RESOURCE = Path(__file__).resolve().parents[1]


def simulate(times_s, discharge_current_A, initial_soc=1.0, capacity_Ah=2.132, temperature_C=25.0):
    times = np.asarray(times_s, dtype=float)
    currents = np.asarray(discharge_current_A, dtype=float)
    if times.ndim != 1 or currents.shape != times.shape or len(times) < 2:
        raise ValueError('Provide equal one-dimensional time and current arrays')
    if not np.isfinite(times).all() or not np.isfinite(currents).all():
        raise ValueError('Nonfinite input')
    if times[0] != 0 or times[-1] <= 0 or np.any(np.diff(times) < 0):
        raise ValueError('Time must start at zero and be nondecreasing; duplicate times retained')
    if np.any(currents < 0):
        raise ValueError('This release only covers discharge/rest; positive discharge current required')
    if not np.isfinite(initial_soc) or not 0.05 <= initial_soc <= 1.01:
        raise ValueError('Initial SOC outside parameter domain [0.05,1.01]')
    if capacity_Ah != 2.132 or temperature_C != 25.0:
        raise ValueError('Shipped reference parameters cover only Q=2.132Ah and isothermal 25C')
    simulator = TheveninModel(str(RESOURCE/'parameters/voltage_25c_ocv.csv'),
                             str(RESOURCE/'parameters/voltage_25c_params.csv'), capacity_Ah)
    currentfunc = lambda t: np.interp(t, times, currents, 0)
    evaluation_times = np.unique(times)
    solution = solve_ivp(simulator.get_ode_rhs(currentfunc,temperature_C),[0,float(times[-1])],
                         np.r_[initial_soc,temperature_C,0.0,0.0],max_step=2.0,
                         atol=1e-5,rtol=1e-5,method='RK45',t_eval=evaluation_times)
    if not solution.success:
        raise RuntimeError(solution.message)
    ts=solution.t
    soc,temp,vrc=solution.y[0],solution.y[1],solution.y[2:]
    inputs=np.array([currentfunc(t) for t in ts])
    voltage=simulator._ocv_lut(temp,soc)-inputs*simulator._r_luts[0](temp,soc)-vrc.sum(axis=0)
    if not np.array_equal(ts, evaluation_times) or not np.isfinite(voltage).all():
        raise RuntimeError('Incomplete or nonfinite solution; no clipping/cropping performed')
    if not np.isfinite(soc).all() or soc.min()<0.05 or soc.max()>1.01:
        raise RuntimeError('SOC outside parameter domain; no extrapolation performed')
    r0_voltage = simulator._ocv_lut(temp,soc)-inputs*simulator._r_luts[0](temp,soc)
    return {'time_s':ts, 'current_discharge_A':inputs, 'voltage_2rc_V':voltage,
            'voltage_r0_V':r0_voltage, 'soc_from_given_initial':soc, 'isothermal_C':temp,
            'vrc1_V':vrc[0], 'vrc2_V':vrc[1]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--initial-soc',type=float,default=1.0)
    args=parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    with args.input.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        if set(reader.fieldnames or []) != {'time_s','current_discharge_A'}:
            raise ValueError('Input columns must be exactly time_s,current_discharge_A; no voltage target input')
        rows=list(reader)
    values=simulate([float(r['time_s']) for r in rows], [float(r['current_discharge_A']) for r in rows],args.initial_soc)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',newline='',encoding='utf-8') as f:
        writer=csv.writer(f)
        writer.writerow(values)
        writer.writerows(zip(*values.values()))
    print(json.dumps({'points':len(values['time_s']),'output':str(args.output),
                      'scope':'given-current and given-initial-SOC voltage calculation; no SOC/capacity estimation'}))


if __name__=='__main__':
    main()
