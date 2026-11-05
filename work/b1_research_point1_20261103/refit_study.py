from study import *

plan=dict(draws=99,seed_offset=90335000,scope='all16savednewfinalcohorts',fixed_bandwidth=True,
    selection='no tuning; all success/failure and all grids retained',coverage='empirical finite-grid observation, only4independentseedblocks; not formal guarantee')
save(HERE/'refit_plan.json',plan)
rows=[]
for i,row in enumerate(json.loads((HERE/'final/summary.json').read_text(encoding='utf-8'))['rows']):
    folder=HERE/'final'/f"{row['seed']}-{row['mechanism']}";m=load_research_point_one(folder/'model.json')
    r=refit_curve_uncertainty(m,GRID,draws=99,seed=plan['seed_offset']+i,target_contrast=120.)
    save(folder/'refit_uncertainty.json',r);t=json.loads((folder/'truth.json').read_text(encoding='utf-8'))
    contained=None
    if r.get('lower') is not None:
        contained=bool(np.all(np.asarray(r['lower'])<=t['contrasts']) and np.all(np.asarray(r['upper'])>=t['contrasts']))
    item=dict(seed=row['seed'],mechanism=row['mechanism'],status=r['status'],success_draws=r['success_draws'],failed_draws=r['failed_draws'],
        whole_grid_truth_contained=contained,band_valid_for_use=r.get('band_valid_for_use',False))
    rows.append(item);print('refit',json.dumps(item),flush=True)
save(HERE/'refit_summary.json',dict(plan=plan,rows=rows,complete_cohorts=sum(r['status']=='complete' for r in rows),
    incomplete_cohorts=sum(r['status']!='complete' for r in rows),all_draws_attempted=99*len(rows),
    truth_containment_not_certified_coverage=True))
