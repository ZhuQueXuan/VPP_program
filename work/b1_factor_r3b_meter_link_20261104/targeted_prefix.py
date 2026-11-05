"""Find a small dynamic-tariff slice inside the same official ZIP."""
import json
import re
import struct
import sys
import zlib
from hashlib import sha256
from pathlib import Path

sys.dont_write_bytecode = True
from range_fetch import CurlArchiveRanges, digest, inspect_metadata, is_dynamic, save_file


BASE = Path(__file__).resolve().parent
ORIGINAL = BASE / 'original'


def members():
    directory = (ORIGINAL / 'zip_central_directory.bin').read_bytes()
    index = 0
    result = {}
    while index < len(directory):
        assert directory[index:index+4] == b'PK\x01\x02'
        packed = struct.unpack_from('<I', directory, index + 20)[0]
        size = struct.unpack_from('<I', directory, index + 24)[0]
        lengths = struct.unpack_from('<HHH', directory, index + 28)
        offset = struct.unpack_from('<I', directory, index + 42)[0]
        name = directory[index+46:index+46+lengths[0]].decode('ascii')
        found = re.search(r'_(\d+)\.csv$', name)
        if found:
            result[int(found[1])] = {'name': name, 'offset': offset, 'compressed_bytes': packed, 'expanded_bytes': size}
        index += 46 + sum(lengths)
    return result


def compressed_part(data):
    assert data[:4] == b'PK\x03\x04'
    flags, method = struct.unpack_from('<HH', data, 6)
    assert method == 8 and not (flags & 1)
    n, extra = struct.unpack_from('<HH', data, 26)
    return data[30+n+extra:]


def expanded(packed):
    stream = zlib.decompressobj(-15)
    raw = stream.decompress(packed)
    final = raw.rfind(b'\n') + 1
    return raw[:final], len(raw) - final, stream.eof


def collect(conditions, receipt):
    catalogue = members()
    network = CurlArchiveRanges(receipt['range_requests'])
    remainder = conditions['maximum_network_bytes_including_previous_ranges'] - conditions['previous_received_range_bytes']
    for index in conditions['fixed_probe_member_order']:
        item = catalogue[index]
        amount = conditions['probe_bytes_including_local_header']
        if remainder < amount:
            break
        _, probe = network.get(item['offset'], amount)
        remainder -= amount
        file = f'target_probe_{index}.bin'
        save_file(file, probe)
        packed = compressed_part(probe)
        data, tail, eof = expanded(packed)
        meta = inspect_metadata(data)
        group_counts = {}
        dynamic = [h for h, row in meta['household_metadata'].items() if is_dynamic(set(row['labels']))]
        for row in meta['household_metadata'].values():
            label = '|'.join(row['labels'])
            group_counts[label] = group_counts.get(label, 0) + 1
        receipt['probes'].append({**item, 'file': file, 'prefix_bytes': amount, 'decoded_complete_rows': meta['records'],
                                  'first_id': min(meta['household_metadata'], default=None),
                                  'last_id': max(meta['household_metadata'], default=None), 'groups_by_household': group_counts,
                                  'dynamic_ids': dynamic, 'truncated_last_line_bytes': tail})
        if not dynamic:
            continue
        extension_file = None
        if len(meta['dToU_full_range']) < 2:
            extra = min(remainder, item['compressed_bytes'] - len(packed) - 1)
            if extra > 0:
                _, extension = network.get(item['offset'] + len(probe), extra)
                remainder -= extra
                extension_file = f'target_extension_{index}.bin'
                save_file(extension_file, extension)
                packed += extension
                data, tail, eof = expanded(packed)
                meta = inspect_metadata(data)
        receipt['prefix_member'] = {**item, 'probe_file': file, 'extension_file': extension_file,
                                    'downloaded_deflate_bytes': len(packed), 'expanded_complete_sha256': sha256(data).hexdigest(),
                                    'truncated_last_line_bytes': tail, 'deflate_eof': eof, 'full_crc_verified': False, **meta}
        receipt['selected_source'] = 'official_zip_partial_member'
        break
    receipt['unused_network_bytes'] = remainder
    receipt['status'] = 'acquired' if 'prefix_member' in receipt else 'stopped_no_dynamic_prefix'


if __name__ == '__main__':
    amendment = BASE / 'targeted_amendment.json'
    spec = json.loads(amendment.read_text(encoding='utf-8'))
    initial = json.loads((BASE / 'source_access_curl.json').read_text(encoding='utf-8'))
    assert spec['previous_received_range_bytes'] == sum(int(r['content_length']) for r in initial['range_requests'])
    assert all(m['dToU_full_range'] == [] for m in initial['members'])
    receipt = {'protocol_sha256': digest(BASE / 'protocol.json'), 'amendment_sha256': digest(amendment),
               'range_requests': [], 'probes': []}
    try:
        collect(spec, receipt)
    except (OSError, ValueError, struct.error, zlib.error) as error:
        receipt['status'] = 'stopped_error'
        receipt['error'] = str(error)
    with (BASE / 'targeted_access.json').open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(receipt['status'], receipt.get('error', ''),
          [(x['name'], x['first_id'], x['last_id'], x['groups_by_household']) for x in receipt['probes']],
          receipt.get('prefix_member', {}).get('dToU_full_range'))
