"""Independent Decimal/XML source verification; no audit-runner import or model."""
from pathlib import Path
from decimal import Decimal, getcontext
from collections import Counter
from itertools import groupby
import csv
import argparse
import datetime
import hashlib
import json
import re
import zipfile
import xml.etree.ElementTree as ET

getcontext().prec = 40
BASE = Path(__file__).resolve().parent
ROOT = BASE.parent.parent
TOL = Decimal('1e-8')
checks = Counter()
largest_difference = Decimal(0)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path, raw=False):
    kw = {'parse_float': Decimal}
    if raw:
        kw['parse_int'] = Decimal
    return json.loads(path.read_text(encoding='utf-8'), **kw)


def number(value):
    return isinstance(value, (Decimal, int)) and not isinstance(value, bool)


def dec(value):
    return value if isinstance(value, Decimal) else Decimal(value)


def good(value):
    return number(value) and dec(value).is_finite() and value != -127


def check(actual, expected, where):
    global largest_difference
    if isinstance(expected, dict):
        assert set(actual) == set(expected), ('keys', where, set(actual) ^ set(expected))
        for key, value in expected.items():
            check(actual[key], value, where + '/' + str(key))
    elif isinstance(expected, list):
        assert len(actual) == len(expected), ('length', where, len(actual), len(expected))
        for index, value in enumerate(expected):
            check(actual[index], value, where + '/' + str(index))
    elif isinstance(expected, Decimal):
        assert number(actual), ('not numeric', where, actual)
        difference = abs(dec(actual) - expected)
        assert difference <= TOL, ('numeric', where, actual, expected, difference)
        largest_difference = max(largest_difference, difference)
        checks['numeric_tolerance'] += 1
    else:
        assert actual == expected, ('exact', where, actual, expected)
        checks['exact'] += 1


def describe(values):
    finite = [dec(x) for x in values if good(x)]
    total = sum(finite, Decimal(0))
    return dict(n=len(values), valid=len(finite), null=sum(x is None for x in values),
                nonfinite=sum(number(x) and not dec(x).is_finite() for x in values),
                sentinel_minus127=sum(x == -127 for x in values),
                nonnumeric=sum(not number(x) for x in values),
                zero=sum(x == 0 for x in finite), negative_valid=sum(x < 0 for x in finite),
                min=min(finite) if finite else None, max=max(finite) if finite else None,
                sum_valid=total if finite else None, mean_valid=total/len(finite) if finite else None)


def seconds(delta):
    # datetime arithmetic uses whole source seconds; no float conversion.
    return Decimal(delta.days*86400 + delta.seconds) + Decimal(delta.microseconds)/1000000


def keyed_counts(values):
    return {str(float(k)): v for k, v in Counter(values).items()}


def serial(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def xlsx_cells(path):
    ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as archive:
        shared = ET.fromstring(archive.read('xl/sharedStrings.xml'))
        texts = [''.join(e.itertext()) for e in shared.findall('m:si', ns)]
        sheet = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
        cells = {}
        for cell in sheet.findall('.//m:sheetData/m:row/m:c', ns):
            value = cell.find('m:v', ns)
            text = value.text if value is not None else None
            if cell.get('t') == 's' and text is not None:
                text = texts[int(text)]
            cells[cell.get('r')] = text
    return cells


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--audit-runs', nargs=2, default=['DRAW_SOURCE_04', 'DRAW_SOURCE_05'])
    parser.add_argument('--run-id', default='VERIFY_DRAW_SOURCE_01')
    args = parser.parse_args()
    config_path = BASE/'draw_evidence_protocol_v1.json'
    cfg = load(config_path)
    run = BASE/'runs'/args.audit_runs[0]
    repeated = BASE/'runs'/args.audit_runs[1]
    receipt = load(run/'receipt.json')
    check(receipt['protocol_sha256'], digest(config_path), 'protocol')
    check(digest(run/'protocol_snapshot.json'), digest(config_path), 'snapshot')
    assert cfg['model_experiment'] is False
    assert repeated.is_dir(), 'Both audit runs must finish before verification'
    repeated_receipt = load(repeated/'receipt.json')
    check(repeated_receipt['status'], receipt['status'], 'repeat status')
    check(repeated_receipt['script_sha256'], receipt['script_sha256'], 'repeat code')
    check(repeated_receipt['protocol_sha256'], receipt['protocol_sha256'], 'repeat protocol')
    check(receipt['script_sha256'], digest(BASE/'audit_draw_evidence.py'), 'audit identity only')
    repeat_hashes = {}
    for name, expected in receipt['outputs'].items():
        check(digest(run/name), expected, 'output identity/'+name)
        check(repeated_receipt['outputs'][name], expected, 'repeat receipt/'+name)
        check(digest(repeated/name), expected, 'repeat artifact/'+name)
        assert (run/name).read_bytes() == (repeated/name).read_bytes(), name
        repeat_hashes[name] = expected

    dictionary_path = BASE/'downloads/DICTIONARY_01/Dataset descriptions.xlsx'
    paper_path = BASE/'downloads/DICTIONARY_01/data_paper.xml'
    check(digest(dictionary_path), receipt['source_dictionary_sha256'], 'dictionary identity')
    check(digest(paper_path), receipt['paper_xml_sha256'], 'paper identity')
    cells = xlsx_cells(dictionary_path)
    columns = sorted((k[:-1] for k in cells if k.endswith('2') and k[:-1].isalpha()),
                     key=lambda c: sum((ord(x)-64)*26**i for i,x in enumerate(c[::-1])))
    dictionary = [{'description': cells[c+'2'], 'unit_format': cells[c+'5']} for c in columns if c != 'A']
    # Openpyxl decodes the original replacement sequence as the degree symbol.
    for entry in dictionary:
        if entry['unit_format'] == '\ufffd\ufffdC':
            entry['unit_format'] = '\u00b0C'
    check(load(run/'dictionary_readonly.json'), dictionary, 'independent zip/xml dictionary')
    expected_units = {'PowerConsumed': ('S', 'Wh'), 'WaterConsumed': ('T', 'mL'),
                      'TotalWaterConsumed': ('U', 'L'), 'DesiredFlowRate': ('F', 'l/min')}
    for raw_name, (column, unit) in expected_units.items():
        check(cells[column+'5'], unit, 'dictionary original unit/'+raw_name)
    root = ET.parse(paper_path).getroot()
    tables = [''.join(e.itertext()) for e in root.iter('table-wrap')]
    check(load(run/'paper_tables.json'), tables, 'independent paper table extraction')
    assert any('Energy usage per sample' in t and 'Water usage per sample' in t for t in tables)

    fresh_path = BASE/'downloads/DRAW_METADATA_20261017_01/dataset.json'
    check(digest(fresh_path), receipt['fresh_metadata_sha256'], 'metadata identity')
    meta = load(fresh_path)
    published = {f['filename']: f for f in meta['files']}
    summary = load(run/'source_summary.json')
    check(summary['scope'], cfg['purpose'], 'purpose')
    check(summary['admission_boundaries'], cfg['admission'], 'admission')
    actual_files = {s['file']: s for s in summary['files']}
    check(list(actual_files), cfg['files'], 'file order')
    with (run/'rows.csv').open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames
        exported = list(reader)
    cursor = 0
    expected_flags = []
    evidence = []
    state_columns = [c for c in columns if cells.get(c+'5') == 'Bool']
    # The dictionary's Boolean block precedes all differently ordered temperature columns.
    state_names = ['ChamberAirTempReg', 'GeyserWaterTempReg', 'InletWaterTempReg', 'FlowRateReg',
                   'WaterScheduleControl', 'PowerScheduleControl', 'ChamberHeatingFans',
                   'ChamberVentingFans', 'CirculationFans', 'ChamberHeatingElement',
                   'WaterValveState', 'GeyserHeatingFlag']
    assert len(state_columns) == len(state_names)
    for filename in cfg['files']:
        path = BASE/'downloads/CLOCK_CANDIDATES_01'/filename
        raw = load(path, raw=True)
        trace = raw['Trace'] if 'Trace' in raw else raw['TraceCollection']
        check(digest(path), published[filename]['content_details']['sha256_hash'], 'official source hash')
        check(path.stat().st_size, published[filename]['size'], 'official source bytes')
        check(receipt['source_files'][filename], digest(path), 'receipt source hash')
        assert set(trace) == set(raw['TraceNames'])
        assert len(trace) == raw['NumberOfTraceEntries']
        length = len(trace['TimeStamp'])
        assert all(len(values) == length for values in trace.values())
        unit_ids = [i for i, text in enumerate(trace['TimeStamp']) if text == 'YYYY-MM-DDTHH:mm:ss']
        expected_flags += [{'file':filename, 'row':i, 'kind':'explicit_unit_row',
                            'source_values':{k:trace[k][i] for k in trace}} for i in unit_ids]
        indices = [i for i in range(length) if i not in unit_ids]
        times = {i: datetime.datetime.strptime(trace['TimeStamp'][i], '%Y-%m-%dT%H:%M:%S') for i in indices}
        step = dec(raw['SamplePeriod'])
        assert step > 0
        columns_numeric = [k for k in trace if k != 'TimeStamp']
        selected = [key for key in header if key in trace]
        assert len(header) == len(selected) + 8  # file,row,time,elapsed,delta,two normalizations,flags
        stats = {name: describe([trace[name][i] for i in indices]) for name in columns_numeric}
        intervals = [seconds(times[j]-times[i]) for i,j in zip(indices, indices[1:])]
        invalid = [{'row':i, 'field':k, 'value':trace[k][i]} for i in indices for k in columns_numeric if not good(trace[k][i])]
        invalid_states = [{'row':i, 'field':k, 'value':trace[k][i]} for i in indices for k in state_names if trace[k][i] not in (0,1)]
        expected_flags += [{'file':filename, **v} for v in invalid + invalid_states]
        energy = {i: trace['PowerConsumed'][i] for i in indices}
        water = {i: trace['WaterConsumed'][i] for i in indices}
        counter = {i: trace['TotalWaterConsumed'][i] for i in indices}
        normal_energy = [dec(energy[i])*3600/step if good(energy[i]) else None for i in indices]
        normal_water = [dec(water[i])*60/(1000*step) if good(water[i]) else None for i in indices]
        for j,i in enumerate(indices):
            row = exported[cursor]
            cursor += 1
            check(row['file'], filename, 'csv/file')
            check(int(row['source_row']), i, 'csv/source row')
            check(row['timestamp'], trace['TimeStamp'][i], 'csv/time')
            check(Decimal(row['elapsed_s']), seconds(times[i]-times[indices[0]]), 'csv/elapsed')
            check(Decimal(row['previous_interval_s']) if row['previous_interval_s'] else None,
                  intervals[j-1] if j else None, 'csv/interval')
            for key in selected:
                if good(trace[key][i]) or number(trace[key][i]):
                    check(Decimal(row[key]), dec(trace[key][i]), 'csv/raw/'+key)
                else:
                    check(row[key], '' if trace[key][i] is None else str(trace[key][i]), 'csv/raw invalid/'+key)
            check(Decimal(row['energy_nominal_equivalent_W']) if row['energy_nominal_equivalent_W'] else None,
                  normal_energy[j], 'csv/nominal energy')
            check(Decimal(row['water_nominal_equivalent_Lmin']) if row['water_nominal_equivalent_Lmin'] else None,
                  normal_water[j], 'csv/nominal water')
            check(row['selected_invalid_fields'], ';'.join(k for k in selected if not good(trace[k][i])), 'csv/invalid')
        water_segments = []
        positive_indices = []
        for is_positive, group in groupby(indices, key=lambda i: good(water[i]) and water[i] > 0):
            segment = list(group)
            if not is_positive:
                continue
            positive_indices += segment
            a,b = segment[0],segment[-1]
            water_segments.append(dict(first_source_row=a, last_source_row=b, first=times[a].isoformat(),
                                       last=times[b].isoformat(), n=len(segment), span_s=seconds(times[b]-times[a]),
                                       sum_water_mL=sum((dec(water[i]) for i in segment), Decimal(0))))
        counter_offsets = []
        for offset in (-1,0,1):
            residuals = []
            for j in range(1,len(indices)):
                if not 0 <= j+offset < len(indices):
                    continue
                before,now,ref = indices[j-1],indices[j],indices[j+offset]
                if good(counter[before]) and good(counter[now]) and good(water[ref]):
                    residuals.append(abs((dec(counter[now])-dec(counter[before]))*1000-dec(water[ref])))
            counter_offsets.append(dict(water_index_offset=offset, n=len(residuals),
                                        mean_absolute_difference_mL=sum(residuals,Decimal(0))/len(residuals) if residuals else None,
                                        max_absolute_difference_mL=max(residuals) if residuals else None))
        groups = []
        for key, values in [('GeyserHeatingFlag',[0,1]), ('WaterValveState',[0,1]),
                            ('water_status',['positive','zero','invalid']), ('energy_status',['positive','zero','invalid'])]:
            for value in values:
                if key in state_names:
                    members = [i for i in indices if trace[key][i] == value]
                else:
                    data = water if key == 'water_status' else energy
                    members = [i for i in indices if ('invalid' if not good(data[i]) else
                               'positive' if data[i]>0 else 'zero' if data[i]==0 else 'negative') == value]
                groups.append(dict(group=key,value=value,n=len(members),
                                   energy_Wh_sum=sum((dec(energy[i]) for i in members if good(energy[i])),Decimal(0)) if members else None,
                                   water_mL_sum=sum((dec(water[i]) for i in members if good(water[i])),Decimal(0)) if members else None))
        result = dict(file=filename, official_id=published[filename]['id'], bytes=path.stat().st_size,
                      sha256=digest(path),raw_entries=length,unit_source_rows=unit_ids,data_rows=len(indices),trace_fields=len(trace),
                      first=times[indices[0]].isoformat(),last=times[indices[-1]].isoformat(),
                      span_s=seconds(times[indices[-1]]-times[indices[0]]),timezone='not supplied',
                      sample_period_metadata_s=step,interval_counts_s=keyed_counts(intervals),
                      duplicate_time_count=len(indices)-len(set(times.values())),backward_steps=sum(x<0 for x in intervals),
                      non_nominal_intervals=sum(x!=step for x in intervals),field_quality=stats,
                      all_invalid_numeric_cells=len(invalid),invalid_state_cells=invalid_states,
                      state_counts={k:keyed_counts([trace[k][i] for i in indices]) for k in state_names},
                      first_data_sample={k:trace[k][indices[0]] for k in selected},
                      last_data_sample={k:trace[k][indices[-1]] for k in selected},
                      interval_energy_sum_including_first_Wh=sum((dec(x) for x in energy.values() if good(x)),Decimal(0)),
                      interval_water_sum_including_first_mL=sum((dec(x) for x in water.values() if good(x)),Decimal(0)),
                      counter_first_L=counter[indices[0]],counter_last_L=counter[indices[-1]],
                      counter_negative_steps=sum(counter[b]<counter[a] for a,b in zip(indices,indices[1:]) if good(counter[a]) and good(counter[b])),
                      counter_alignment_all_offsets=counter_offsets,positive_water_runs=water_segments,
                      observed_suffix_after_last_positive_water_s=seconds(times[indices[-1]]-times[positive_indices[-1]]) if positive_indices else None,
                      heating1_energy0_rows=[i for i in indices if trace['GeyserHeatingFlag'][i]==1 and energy[i]==0],
                      valve0_positive_water_rows=[i for i in indices if trace['WaterValveState'][i]==0 and good(water[i]) and water[i]>0],
                      valve1_zero_water_rows=[i for i in indices if trace['WaterValveState'][i]==1 and water[i]==0],
                      selected_invalid_source_rows=[i for i in indices if any(not good(trace[k][i]) for k in selected)],
                      energy_nominal_equivalent_W=describe(normal_energy),water_nominal_equivalent_Lmin=describe(normal_water),groups=groups)
        check(actual_files[filename],result,'all summary/'+filename)
        native_types = json.loads(path.read_text(encoding='utf-8'))
        native_trace = native_types.get('Trace', native_types.get('TraceCollection'))
        unit_conflicts = [{'source_row':i,'field':key,'original_unit':trace[key][i],
                           'dictionary_unit':unit} for i in unit_ids
                         for key,(_,unit) in expected_units.items()
                         if str(trace[key][i]).lower() != unit.lower()]
        evidence.append(dict(file=filename,rows=len(indices),all_numeric_fields=len(columns_numeric),
                             all_numeric_cells=len(indices)*len(columns_numeric),
                             source_native_type_counts={k:dict(Counter(type(native_trace[k][i]).__name__ for i in indices)) for k in trace},
                             field_lengths={k:len(v) for k,v in trace.items()},
                             raw_unit_rows=[{'source_row':i, 'fields':{k:trace[k][i] for k in trace}} for i in unit_ids],
                             original_unit_row_dictionary_conflicts=unit_conflicts,
                             raw_number_of_measurements=raw['NumberOfMeasurements'],
                             positive_water_rows=len(positive_indices),
                             last_positive_water_source_row=positive_indices[-1] if positive_indices else None,
                             observed_suffix_s=result['observed_suffix_after_last_positive_water_s'],
                             measurement_alignment_established=False,thermal_capacity_or_command_delay_admitted=False))
    check(cursor,len(exported),'all exported rows')
    check(load(run/'raw_quality_flags.json'),expected_flags,'all raw quality flags')
    release_files = receipt['original_release_files']
    official_release_inventory = {}
    for resource, name in [('lithium_ion_storage','release_validation.json'),
                           ('distributed_photovoltaic','release_validation_v1_2.json'),
                           ('ev_charging','release_validation_v1_1.json'),
                           ('air_conditioning','release_validation_v1_1.json'),
                           ('wind_power','release_validation_v1_1.json'),
                           ('electric_water_heating','release_validation.json')]:
        release_base = ROOT/'resource_research_results'/resource
        current = load(release_base/'results'/name)
        for name, h in current.get('verified_files',current.get('artifact_sha256',{})).items():
            official_release_inventory[str((release_base/name).relative_to(ROOT))] = h
    check(release_files,official_release_inventory,'current six release receipt inventory')
    for path, expected in release_files.items():
        check(digest(ROOT/path),expected,'released artifact/'+path)
    check(repeated_receipt['original_release_files'],release_files,'repeat release fingerprints')
    check(digest(BASE/'temperature_protocol_v1.json'),receipt['original_temperature_protocol_sha256'],'D067 protocol')
    destination = BASE/'runs'/args.run_id
    destination.mkdir(exist_ok=False)
    final = dict(status='passed_independent_arithmetic_with_disclosed_unit_conflict',
                 date='2026-10-17',verifier_sha256=digest(Path(__file__)),
                 protocol_sha256=digest(config_path), absolute_numeric_tolerance=str(TOL),
                 maximum_numeric_difference=str(largest_difference),checks=dict(checks),
                 total_data_rows=cursor,all_original_numeric_fields_checked=True,
                 all_csv_raw_and_normalized_fields_checked=True,all_state_groups_and_counter_offsets_checked=True,
                 all_source_quality_flags_checked=len(expected_flags),original_release_files_checked=len(release_files),
                 audited_runs=args.audit_runs,all_scientific_artifacts_byte_identical=repeat_hashes,
                 files=evidence,
                 source_summary_sha256=digest(run/'source_summary.json'),
                 rows_sha256=digest(run/'rows.csv'),raw_flags_sha256=digest(run/'raw_quality_flags.json'),
                 source_dictionary_sha256=digest(dictionary_path),paper_xml_sha256=digest(paper_path),
                 independent_method='stdlib raw JSON numeric lexemes as Decimal; direct datetime source labels; groupby positive runs; independent zip/XML XLSX reader; no audit import',
                 unit_conflict='Original NoHeating unit row labels TotalWaterConsumed as mL while original XLSX/paper uses L. Both files publish zero for the entire counter. Difference*1000 is only dictionary-L conditional diagnostic, not verified counter unit or water balance. Conflict preserved without conversion choice.',
                 physical_limits=['No independent timing/calibration truth; nominal W and L/min depend on SamplePeriod only.',
                                  'Valve and event-total zero versus positive interval water remains unresolved, not proven actual closed valve.',
                                  'Source unit-row mL versus dictionary L for TotalWaterConsumed remains unresolved; all-zero counter hides numerical consequence.',
                                  'Different dates/initial states are not randomized With/NoHeating interventions.',
                                  'End-of-file positive water is right censoring; no verified recovery duration.',
                                  'No thermal balance, efficiency, available capacity, human authorization, command delay or causal effect admitted.'])
    (destination/'receipt.json').write_text(json.dumps(final,ensure_ascii=False,indent=2,default=serial)+'\n',encoding='utf-8')
    print(json.dumps({k:final[k] for k in ('status','total_data_rows','maximum_numeric_difference','checks','original_release_files_checked')},ensure_ascii=False))


if __name__ == '__main__':
    main()
