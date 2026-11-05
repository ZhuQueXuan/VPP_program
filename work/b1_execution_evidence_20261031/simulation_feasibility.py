"""Truth-known100ms information checks; no feature algorithm or winner fitting.

Matched observations under different latent causes prove ambiguity. Optional
independent measurement is hypothetical; shared faults break that separation.
"""
from common import *

def main():
    write('simulation_protocol.json',dict(purpose='Small information-feasibility supplement because real100ms action/sensor-fault truth is not established. Not a benchmark performance claim.',
        seeds=[7653100,7653101,7653102,7653103],observed_grid_ms=100,window_s=[-5,15],task_s=[0,10],fine_generator_ms=1,
        shapes=['pulse100ms','pulse500ms','pulse2s','pulse5s','ramp_hold','slow_drift'],
        labels='For every shape produce actual physical change and primary measurement-only corruption with identical primary observations and identical command. Short-glitch vs persistent-fault label derives from declared generator, not fitted appearance.',
        second_meter='Optional simulated independent meter, not secretly available KIT data. Also include common-mode corruption of both meters.',
        command='Identical requested step for every paired cause: t0..10s,1.5kW request. Command does not reveal class.',
        physical='Single-phase230V,baseline3.3kW,positive bounded power.1ms latent shape integrated to100ms; no interpolation of field data.',
        noise='Gaussian declared sigma.05kW per meter. Shared paired noise for exact indistinguishability proof, independent meters under optional scenario. Not calibrated field fault prevalence/distribution.',
        metrics='Identity of observable primary current/power/command and optional independent-channel difference. No classifier, filtering, process fit or adoption gate.',
        scope='20s window aligned to existing100ms case scale, not30min EV process validation. Extremely short/persistent anomalies and true short responses all kept.'))
    starts_us=np.arange(-5000000,15000000,100000,dtype=np.int64);fine_s=(-5000000+np.arange(20000)*1000+500)/1e6
    starts_s=starts_us/1e6;baseline=3.3;command=np.where((starts_s>=0)&(starts_s<10),baseline-1.5,baseline)
    pairs=[];samples=[];out=HERE/'simulation';out.mkdir(exist_ok=False)
    shapes=read(HERE/'simulation_protocol.json')['shapes']
    for seed in read(HERE/'simulation_protocol.json')['seeds']:
        rng=np.random.default_rng(seed)
        for shape in shapes:
            amplitude=float(rng.uniform(.45,1.2));latent=np.zeros(len(fine_s));x=fine_s-3.
            if shape.startswith('pulse'):
                duration={'pulse100ms':.1,'pulse500ms':.5,'pulse2s':2.,'pulse5s':5.}[shape];latent[(x>=0)&(x<duration)]=amplitude
            elif shape=='ramp_hold':
                latent[(x>=0)&(x<1)]=amplitude*x[(x>=0)&(x<1)];latent[(x>=1)&(x<4)]=amplitude;latent[(x>=4)&(x<5)]=amplitude*(5-x[(x>=4)&(x<5)])
            else:latent[(x>=0)&(x<5)]=amplitude*x[(x>=0)&(x<5)]/5
            change=latent.reshape(200,100).mean(axis=1);physical_actual=baseline-change;physical_no_action=np.repeat(baseline,200)
            primary_noise=rng.normal(0,.05,200);secondary_noise=rng.normal(0,.05,200)
            observed=baseline-change+primary_noise
            actual_secondary=physical_actual+secondary_noise;fault_secondary=physical_no_action+secondary_noise
            common_fault_secondary=physical_no_action-change+secondary_noise
            assert np.allclose(actual_secondary,common_fault_secondary,atol=0,rtol=0)
            base=f'{seed}-{shape}';records={}
            for cause in ['actual_response','primary_meter_fault','common_mode_meter_fault']:
                clean=physical_actual if cause=='actual_response' else physical_no_action
                secondary=actual_secondary if cause=='actual_response' else fault_secondary if cause=='primary_meter_fault' else common_fault_secondary
                path=out/(base+'-'+cause+'.npz')
                with path.open('xb') as f:np.savez_compressed(f,starts_us=starts_us,command_kw=command,
                    primary_power_kw=observed,primary_current_A=observed*1000/230,
                    optional_secondary_meter_kw=secondary,truth_physical_power_kw=clean,
                    truth_physical_response_kw=baseline-clean,truth_primary_measurement_bias_kw=np.zeros(200) if cause=='actual_response' else -change,
                    truth_secondary_measurement_bias_kw=-change if cause=='common_mode_meter_fault' else np.zeros(200))
                records[cause]=path.relative_to(ROOT).as_posix()
                samples.append(dict(sample_id=base+'-'+cause,source='fully_simulated_not_real_label',cause=cause,
                    waveform=shape,seed=seed,raw_path=records[cause],truth_effective_duration_s=float(np.sum((baseline-clean)>=.15)*.1),
                    optional_second_meter_hypothetical=True))
            pairs.append(dict(pair_id=base,shape=shape,amplitude_kw=amplitude,samples=records,
                primary_and_command_identical_for_different_causes=True,
                optional_independent_meter_observation_max_difference_kw=float(np.max(abs(actual_secondary-fault_secondary))),
                common_mode_all_observations_identical=True,
                true_action_duration_s=float(np.sum(change>=.15)*.1)))
    write('simulation_samples.json',samples);write('simulation_pairs.json',pairs)
    write('simulation_feasibility.json',dict(base_waveforms=len(pairs),variant_samples=len(samples),independent_physical_experiments=0,
        grid_ms=100,primary_command_identical_pairs=len(pairs),all_observations_identical_under_common_fault_pairs=len(pairs),
        hypothetical_independent_meter_separates_observations_pairs=sum(r['optional_independent_meter_observation_max_difference_kw']>0 for r in pairs),
        conclusion='Matched100ms ground-truth samples are feasible. Primary current+derived power+command alone cannot universally distinguish these causes. Independent evidence helps only under declared independence/non-common-fault assumptions. No accuracy or real robustness claim.'))
    print(json.dumps(read(HERE/'simulation_feasibility.json')))
if __name__=='__main__':main()
