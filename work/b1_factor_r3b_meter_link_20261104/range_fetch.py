"""Fetch at most two official CSV members via checked HTTP byte ranges."""
import csv
import io
import json
import re
import struct
import subprocess
import sys
import zlib
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


BASE = Path(__file__).resolve().parent
ORIGINAL = BASE / 'original'
URL = 'https://data.london.gov.uk/download/vqm0d/04feba67-f1a3-4563-98d0-f3071e3d56d1/Partitioned%20LCL%20Data.zip'
SMALL_URL = 'https://files.datapress.com/london/dataset/smartmeter-energy-use-data-in-london-households/UKPN-LCL-smartmeter-sample.csv'
FROZEN_PROTOCOL = 'b9ae42f8b1b338002c41466f5a0060f430fb72cd9bbc3ae4a963a2ca2ff6a1c4'
LIMIT = 12 * 1024 * 1024
MIN_TIME = '2013-02-11 00:00:00'
MAX_TIME = '2013-11-22 06:00:00'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def save_file(name, data):
    with (ORIGINAL / name).open('xb') as f:
        f.write(data)


def field_map(names):
    fields = {name.lower().strip(): name for name in names}
    return {'id': fields.get('lclid'), 'group': fields.get('stdortou'), 'time': fields.get('datetime'),
            'kwh': next((name for lower, name in fields.items() if lower.startswith('kwh/hh')), None)}


def csv_reader(data):
    return csv.DictReader(io.TextIOWrapper(io.BytesIO(data), encoding='utf-8-sig', newline=''))


def is_dynamic(labels):
    return len(labels) == 1 and next(iter(labels)).casefold() in ('tou', 'dtou')


def inspect_metadata(data):
    rows = csv_reader(data)
    fields = field_map(rows.fieldnames or [])
    if not fields['id'] or not fields['time'] or not fields['kwh']:
        raise ValueError('Meter source schema not recognized')
    info = {}
    groups = defaultdict(set)
    count = 0
    for row in rows:
        count += 1
        hid, stamp = row[fields['id']], row[fields['time']][:19]
        group = row[fields['group']].strip() if fields['group'] else ''
        groups[hid].add(group)
        if hid in info:
            old_min, old_max = info[hid]
            info[hid] = min(stamp, old_min), max(stamp, old_max)
        else:
            info[hid] = stamp, stamp
    return {'columns': rows.fieldnames, 'records': count,
            'household_metadata': {hid: {'labels': sorted(groups[hid]), 'first': span[0], 'last': span[1]}
                                   for hid, span in sorted(info.items())},
            'dToU_full_range': sorted(hid for hid, span in info.items()
                                      if is_dynamic(groups[hid]) and span[0] <= MIN_TIME and span[1] >= MAX_TIME)}


def response_info(response):
    parts = urlsplit(response.url)
    return {'status': response.status,
            'url': urlunsplit((parts.scheme, parts.netloc, parts.path, '', '')),
            'content_range': response.headers.get('Content-Range'),
            'content_length': response.headers.get('Content-Length'),
            'etag': response.headers.get('ETag'), 'last_modified': response.headers.get('Last-Modified')}


class ArchiveRanges:
    def __init__(self, receipt):
        self.receipt = receipt
        self.version = None

    def get(self, start=None, count=65557):
        byte_range = f'bytes=-{count}' if start is None else f'bytes={start}-{start + count - 1}'
        log = {'request_range': byte_range}
        self.receipt.append(log)
        with urlopen(Request(URL, headers={'Range': byte_range, 'Accept-Encoding': 'identity'}), timeout=25) as response:
            log.update(response_info(response))
            if response.status != 206:
                raise ValueError(f'Range rejected with HTTP {response.status}; body not read')
            match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', log['content_range'] or '')
            if not match:
                raise ValueError('Missing exact Content-Range')
            left, right, total = map(int, match.groups())
            if left != (total - count if start is None else start) or right != left + count - 1:
                raise ValueError('Response covers an unexpected range')
            version = (total, log['etag'], log['last_modified'])
            if not any(version[1:]):
                raise ValueError('No stable ETag or Last-Modified')
            if self.version is None:
                self.version = version
            elif version != self.version:
                raise ValueError('Archive version changed between byte ranges')
            content = response.read(count + 1)
            if len(content) != count:
                raise ValueError('Byte range is incomplete or oversized')
            log['sha256'] = sha256(content).hexdigest()
            return left, content

    def directory(self):
        left, tail = self.get()
        save_file('zip_tail.bin', tail)
        eocd = tail.rfind(b'PK\x05\x06')
        if eocd < 0:
            raise ValueError('ZIP EOCD is absent from suffix')
        _, disk, cd_disk, entries_here, entries, size, offset, comment = struct.unpack_from('<4s4H2LH', tail, eocd)
        if disk or cd_disk or entries_here != entries or eocd + 22 + comment != len(tail) or size > 256 * 1024:
            raise ValueError('ZIP is split, unsupported, or exceeds central-directory budget')
        if offset + size > left + eocd:
            raise ValueError('ZIP central directory overlaps EOCD')
        central = tail[offset - left:offset - left + size] if offset >= left else self.get(offset, size)[1]
        save_file('zip_central_directory.bin', central)
        members = []
        pos = 0
        for _ in range(entries):
            header = struct.unpack_from('<4s6H3L5H2L', central, pos)
            sig, _created, _version, flags, method, _time, _date, crc, packed, length, n, extra, note, disk, _, _, start = header
            if sig != b'PK\x01\x02' or disk:
                raise ValueError('Unsupported central entry')
            name = central[pos + 46:pos + 46 + n].decode('utf-8' if flags & 0x800 else 'cp437')
            members.append({'name': name, 'flags': flags, 'method': method, 'crc32': crc,
                            'compressed_bytes': packed, 'expanded_bytes': length, 'offset': start})
            pos += 46 + n + extra + note
        if pos != size:
            raise ValueError('Directory length mismatch')
        return members

    def member(self, item, index):
        offset = item['offset']
        _, header = self.get(offset, 30)
        magic, _needed, flags, method, _time, _date, _, _, _, name_len, extra_len = struct.unpack('<4s5H3L2H', header)
        if magic != b'PK\x03\x04' or method != 8 or method != item['method'] or flags & 1:
            raise ValueError('Unexpected local ZIP member header')
        _, packed = self.get(offset + 30 + name_len + extra_len, item['compressed_bytes'])
        save_file(f'member_{index:02d}_local_header.bin', header)
        save_file(f'member_{index:02d}_deflate.bin', packed)
        data = zlib.decompress(packed, wbits=-15)
        if len(data) != item['expanded_bytes'] or zlib.crc32(data) != item['crc32']:
            raise ValueError('ZIP member CRC32 or expanded size failed')
        return data


class CurlArchiveRanges(ArchiveRanges):
    VERSION = (795722689, '"f3e020799f8feae94a2d9036dfae3331-152"', '2025-10-21T18:46:36.000Z')

    def get(self, start=None, count=65557):
        total, etag, modified = self.VERSION
        if start is None:
            start = total - count
            source = (ORIGINAL / 'curl_zip_tail.bin').read_bytes()
            if len(source) != count:
                raise ValueError('Cached 206 suffix byte length does not match response')
            self.receipt.append({'request_range': f'bytes={start}-{total - 1}', 'status': 206,
                                 'content_range': f'bytes {start}-{total - 1}/{total}',
                                 'content_length': str(count), 'etag': etag, 'last_modified': modified,
                                 'cached_206_suffix': 'curl_zip_tail.bin', 'sha256': sha256(source).hexdigest()})
            return start, source
        end = start + count - 1
        log = {'request_range': f'bytes={start}-{end}'}
        self.receipt.append(log)
        command = ['curl.exe', '-fLsSi', '--max-redirs', '2', '--connect-timeout', '15', '--max-time', '55',
                   '--max-filesize', str(count), '-H', 'Accept-Encoding: identity', '--range', f'{start}-{end}', URL]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False)
        body = result.stdout
        headers = {}
        while body.startswith(b'HTTP/'):
            text, delimiter, body = body.partition(b'\r\n\r\n')
            if not delimiter:
                raise ValueError('Incomplete HTTP range response header')
            status, *items = text.decode('iso8859-1').split('\r\n')
            log['status'] = int(status.split()[1])
            headers = {line.split(':', 1)[0].lower(): line.split(':', 1)[1].strip() for line in items if ':' in line}
        for field in ('content-range', 'content-length', 'etag', 'last-modified'):
            log[field.replace('-', '_')] = headers.get(field)
        if result.returncode or log.get('status') != 206:
            raise ValueError(f'Range access failed with HTTP {log.get("status")} and curl exit {result.returncode}')
        if log['content_range'] != f'bytes {start}-{end}/{total}' or len(body) != count:
            raise ValueError('Range response does not match the requested byte offsets')
        if log['etag'] != etag or log['last_modified'] != modified:
            raise ValueError('Archive version changed since the 206 suffix probe')
        log['sha256'] = sha256(body).hexdigest()
        return start, body


def collect(receipt, fetch_class):
    sample = ORIGINAL / 'archived_sample.csv'
    if sample.exists():
        source = sample.read_bytes()
        receipt['archived_sample'] = {'url': SMALL_URL, 'file': sample.name, 'bytes': len(source),
                                      'sha256': digest(sample), **inspect_metadata(source)}
        if receipt['archived_sample']['dToU_full_range']:
            receipt['selected_source'] = 'archived_sample'
            return
    else:
        receipt['archived_sample'] = {'url': SMALL_URL, 'file': None}
    archive = fetch_class(receipt['range_requests'])
    all_members = archive.directory()
    csvs = [m for m in all_members if re.search(r'\d+\.csv$', m['name'], flags=re.I)]
    csvs.sort(key=lambda m: (int(re.search(r'(\d+)\.csv$', m['name'], flags=re.I)[1]), m['name']))
    receipt['zip_total_members'] = len(all_members)
    receipt['numbered_csv_members'] = len(csvs)
    if not csvs:
        raise ValueError('No numbered CSV members in official ZIP')
    used = 0
    for index, item in enumerate(csvs[:2], 1):
        used += item['compressed_bytes']
        if used > LIMIT or item['expanded_bytes'] > 96 * 1024 * 1024:
            raise ValueError('Member exceeds frozen byte budget')
        data = archive.member(item, index)
        receipt['members'].append({**item, 'file': f'member_{index:02d}_deflate.bin',
                                   'expanded_sha256': sha256(data).hexdigest(), **inspect_metadata(data)})
        if receipt['members'][-1]['dToU_full_range']:
            break
    receipt['selected_source'] = 'official_partitioned_zip_range'


if __name__ == '__main__':
    assert digest(BASE / 'protocol.json') == FROZEN_PROTOCOL
    receipt = {'protocol_sha256': FROZEN_PROTOCOL, 'official_zip_url': URL, 'range_requests': [], 'members': []}
    curl_mode = '--curl' in sys.argv
    try:
        collect(receipt, CurlArchiveRanges if curl_mode else ArchiveRanges)
        receipt['status'] = 'acquired'
    except (OSError, ValueError, struct.error, zlib.error, subprocess.TimeoutExpired) as error:
        receipt['status'] = 'stopped'
        receipt['error'] = str(error)
    with (BASE / ('source_access_curl.json' if curl_mode else 'source_access.json')).open('x', encoding='utf-8') as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(receipt['status'], receipt.get('error', ''), [(m['name'], m['records'], len(m['dToU_full_range'])) for m in receipt['members']])
