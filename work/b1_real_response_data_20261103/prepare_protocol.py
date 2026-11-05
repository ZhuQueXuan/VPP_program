"""Freeze real-data cohort and time split using assignment metadata only."""
from pathlib import Path
import csv,json,hashlib
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
RAW=ROOT/'data/public_datasets/挪威_iFlex_动态电价试验'

def save(name,value):
    with (HERE/name).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)

if __name__=='__main__':
    with (RAW/'experiment_days.csv').open(encoding='utf-8-sig',newline='') as f:days=list(csv.DictReader(f))
    selected=[r for r in days if r['Participation_Phase']=='Phase_2' and r['Group'] in ('H2','Os_2','Trom_2')]
    assert len(selected)==59 and all(r['Price_signal'] in ('P_2','P_5','P_10','P_15') for r in selected)
    dates=sorted({r['Date'] for r in selected});assert len(dates)==30
    splits={d:'train' if i<20 else 'validation' if i<25 else 'test' for i,d in enumerate(dates)}
    protocol=dict(scope='Real household price-path auxiliary validation dataset, not a replacement for EV continuous incentive/duration target',
        source='https://zenodo.org/records/8248802',license='CC-BY-4.0',phase='Phase_2',
        selection_basis='assignment metadata only; no consumption outcome or algorithm output used to choose cohort or dates',
        pure_P_groups=['H2','Os_2','Trom_2'],observed_price_signals=['P_2','P_5','P_10','P_15'],
        assigned_group_days=59,assigned_dates=30,full_price_path='24 hours; original Hour17/18 vary, other22 identical',
        time_semantics='Preserve original Date/Hour keys and explicitly UTC From; no reinterpretation or rounding of samples',
        notice='Previous source Date at18:00 Europe/Oslo; phase2 event dates before DST switch =>17:00UTC',
        outcomes=['sum of measured Demand_kWh at original source Hour17 and18','sum of measured24 source Date hours'],
        no_truth_labels='Actual consumption only. No individual no-incentive counterfactual, physical effective duration, or gold continuous effect curve.',
        pre_notice_features=['completed preceding24h actual consumption and temperature','completed preceding168h actual consumption',
            'region, group, calendar and full assigned price path'],
        forbidden_as_pre_features=['target-day actual consumption','target-day actual temperature or rolling Temperature24/48/72',
            'survey3 collected after treatment','realized reward or synthetic compensation'],
        splits_by_whole_date=splits,split_counts=dict(train_dates=20,validation_dates=5,test_dates=5),
        independence='group-date assignment and repeated households; hourly records or household-days are not independent randomized prices',
        split_claim='future-date evaluation for known household population; users can recur across time, not unseen-user generalization',
        quality='Keep every designed household event with availability/missing/duplicate/nonfinite flags; do not set missing to zero or select only responders',
        current_stage='Data preparation and design/support audit only; no new model fit, continuous method comparison or causal effect claim.',
        continuous_eligibility=False,why_not='Four actual randomized path intensities, not a continuous scalar-dose experiment. Numeric hourly jitter cannot fill unsupported price gaps.',
        first_part_and_other_algorithms_unchanged=True)
    save('real_data_protocol.json',protocol)
    save('source_before.json',{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in RAW.iterdir() if p.is_file()})
    files=list((ROOT/'B1算法').rglob('*.py'))+list((ROOT/'B1算法').rglob('*.json'))
    save('formal_before.json',{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    with (HERE/'selected_design.csv').open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['Participation_Phase','Price_signal','Date','Group','split'])
        w.writeheader();w.writerows(dict(r,split=splits[r['Date']]) for r in selected)
    print(json.dumps(dict(design_group_days=len(selected),dates=len(dates),date_split=protocol['split_counts'],latest_train=dates[19],latest_validation=dates[24],first_test=dates[25])))
