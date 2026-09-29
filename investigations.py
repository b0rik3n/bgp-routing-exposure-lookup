"""Versioned, bounded evidence bundles and offline BGP snapshot comparisons.

Imports never extract ZIP members or follow URLs. Replay invokes local parsers only.
CAIDA source datasets are referenced, not redistributed in the bundle.
"""
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import platform
import subprocess
import zipfile

from lookup import LookupError, parse_import
from paths import (MAX_PATH_INPUTS, MAX_EVIDENCE, MAX_RIS_ROUTES, PathLookup,
                   parse_path_resource, select_routes, summarize_routes)

SCHEMA = 1
MAX_BUNDLE = 32_000_000
MAX_EXPANDED = 48_000_000
MAX_CAPTURE = 16_000_000
FILES = {'manifest.json', 'investigation.json', 'SUMMARY.txt'}
LIMITATION = ('Replay verifies route selection, normalization, grouping, and saved enrichment application. '
              'It does not independently reparse CAIDA datasets, prove source authenticity, or confirm '
              'a physical connection, traffic flow, or vulnerability. CAIDA source datasets are not bundled.')


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def tool_version():
    root = Path(__file__).parent
    sources = {name: digest((root / name).read_bytes()) for name in
               ('lookup.py', 'paths.py', 'investigations.py')}
    try:
        commit = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                                capture_output=True, text=True, timeout=3, check=True).stdout.strip()
        dirty = bool(subprocess.run(['git', '-C', str(root), 'status', '--porcelain'],
                                   capture_output=True, text=True, timeout=3, check=True).stdout.strip())
    except (OSError, subprocess.SubprocessError):
        commit, dirty = None, None
    return {'commit': commit, 'workingTreeModified': dirty, 'sourceSha256': sources,
            'python': platform.python_version(), 'processingVersion': 1,
            'options': {'maxDisplayedEvidence': MAX_EVIDENCE, 'maxRisRoutes': MAX_RIS_ROUTES}}


class Capture:
    def __init__(self):
        self.records = []
        self.size = 0

    def add(self, item, raw, url, result, relationships):
        # Store exact received RIS bytes; the JSON envelope remains inside them.
        adjacent = {(g['origin'], n['asn']) for g in result.get('groups', []) for n in g['neighbors']}
        relationships = {key: kind for key, kind in relationships.items() if key in adjacent}
        record = {'input': item['input'], 'risBase64': base64.b64encode(raw).decode() if raw else None,
                  'risUrl': url, 'organizations': result.get('asns', {}),
                  'relationships': [[a, b, kind] for (a, b), kind in sorted(relationships.items())]}
        amount = len(encode(record))
        if self.size + amount > MAX_CAPTURE:
            raise LookupError('Investigation evidence exceeds 16 MB. Use fewer inputs or a narrower prefix.')
        self.size += amount
        self.records.append(record)


def capture_snapshot(engine, text, requested, progress):
    capture = Capture()
    payload = engine.lookup(text, requested, progress, capture=capture)
    return {'requestedDate': requested, 'result': payload, 'evidence': capture.records}


def replay_snapshot(snapshot):
    checks, selections = [], []
    for saved, record in zip(snapshot['result']['results'], snapshot['evidence']):
        raw = record['risBase64']
        if not raw or saved['status'] not in ('mapped', 'not_observed'):
            checks.append({'input': saved['input'], 'status': 'unavailable',
                           'reason': 'No successful raw routing response was captured.'})
            selections.append(None)
            continue
        state = json.loads(base64.b64decode(raw, validate=True))['data']
        item = parse_path_resource(record['input'])
        routes, skipped = select_routes(state, item)
        orgs = {int(key): value for key, value in record['organizations'].items()}
        relationships = {(a, b): kind for a, b, kind in record['relationships']}
        groups, names = summarize_routes(routes, orgs, relationships) if routes else ([], {})
        actual = {'groups': groups, 'asns': names, 'skippedPaths': skipped,
                  'status': 'mapped' if routes else 'not_observed'}
        expected = {key: saved.get(key) for key in actual}
        match = actual == expected
        checks.append({'input': saved['input'], 'status': 'match' if match else 'mismatch'})
        selections.append(routes if match else None)
    return checks, selections


def _view(rows):
    result = {}
    for row in rows:
        path = row['path']
        if len(path) < 2:
            continue
        key = (path[-1], path[-2], row['prefix'])
        entry = result.setdefault(key, {'paths': set(), 'peers': set()})
        entry['paths'].add(tuple(path))
        entry['peers'].add(row['source'])
    return result


def differences(before, after):
    left, right = _view(before), _view(after)
    changes = []
    for key in sorted(left.keys() | right.keys()):
        if key not in left:
            label = 'Newly observed adjacency'
        elif key not in right:
            label = 'Previously observed adjacency not seen'
        elif left[key]['paths'] != right[key]['paths']:
            label = 'Observed path changed'
        elif left[key]['peers'] != right[key]['peers']:
            label = 'Observation coverage changed'
        else:
            continue
        a, b = left.get(key, {}), right.get(key, {})
        changes.append({'origin': key[0], 'neighbor': key[1], 'prefix': key[2], 'change': label,
                        'beforePaths': [list(p) for p in sorted(a.get('paths', []))],
                        'afterPaths': [list(p) for p in sorted(b.get('paths', []))],
                        'beforePeers': sorted(a.get('peers', [])), 'afterPeers': sorted(b.get('peers', []))})
    return changes


def compare(snapshots, selections):
    output = []
    first, second = snapshots
    for index, (a, b) in enumerate(zip(*selections)):
        left = first['result']['results'][index]
        right = second['result']['results'][index]
        base = {'input': left['input'], 'beforeObservedAt': left.get('observation', {}).get('observedAt'),
                'afterObservedAt': right.get('observation', {}).get('observedAt')}
        if a is None or b is None:
            output.append({**base, 'status': 'unavailable',
                           'reason': 'One snapshot has no replayable routing evidence; no disappearance is inferred.'})
            continue
        peers_a, peers_b = {r['source'] for r in a}, {r['source'] for r in b}
        common = peers_a & peers_b
        rel_a = {(x, y): kind for x, y, kind in first['evidence'][index]['relationships']}
        rel_b = {(x, y): kind for x, y, kind in second['evidence'][index]['relationships']}
        rel_changes = []
        for origin, neighbor, prefix in sorted(_view(a).keys() & _view(b).keys()):
            old, new = rel_a.get((origin, neighbor), 'unknown'), rel_b.get((origin, neighbor), 'unknown')
            if old != new:
                rel_changes.append({'origin': origin, 'neighbor': neighbor, 'prefix': prefix,
                                    'change': 'Relationship inference changed', 'before': old, 'after': new})
        output.append({**base, 'status': 'compared', 'allChanges': differences(a, b),
                       'commonPeerChanges': differences([r for r in a if r['source'] in common],
                                                        [r for r in b if r['source'] in common]) if common else None,
                       'relationshipChanges': rel_changes,
                       'coverage': {'before': sorted(peers_a), 'after': sorted(peers_b), 'common': sorted(common),
                                    'added': sorted(peers_b - peers_a), 'notSeen': sorted(peers_a - peers_b)},
                       'beforeDirectOriginObservations': sum(len(r['path']) == 1 for r in a),
                       'afterDirectOriginObservations': sum(len(r['path']) == 1 for r in b),
                       'relationshipDates': [r.get('relationships', {}).get('snapshotDate') for r in (left, right)],
                       'warnings': left.get('warnings', []) + right.get('warnings', [])})
    return output


def inspect(data):
    checks, selections = [], []
    for snapshot in data['snapshots']:
        check, selected = replay_snapshot(snapshot)
        checks.append(check)
        selections.append(selected)
    comparison = compare(data['snapshots'], selections) if len(selections) == 2 else None
    current = tool_version()
    return {'kind': 'investigation', 'createdAt': data['createdAt'], 'inputs': data['inputs'],
            'tool': data['tool'], 'replayTool': current,
            'sameProcessingCode': current['sourceSha256'] == data['tool'].get('sourceSha256'),
            'comparisonReplay': ('match' if comparison == data['comparison'] else 'mismatch') if 'comparison' in data else 'not_saved',
            'snapshots': [s['result'] for s in data['snapshots']],
            'replay': checks, 'limitation': LIMITATION,
            'comparison': comparison,
            'coverageMeaning': 'Common peers reported selected target routes at both times; this is not a census of active RIS sessions. Restricting to common peers can hide losses and does not remove all visibility bias.',
            'integrityMeaning': 'SHA-256 checks detect accidental changes, not fabricated evidence or source authenticity.'}


def build(engine, text, dates, progress=lambda _: None):
    items = parse_import(text, parse_path_resource, MAX_PATH_INPUTS)
    if len(dates) not in (1, 2):
        raise LookupError('Choose one observation date or two comparison dates.')
    if len(dates) == 2 and (any(not isinstance(d, str) for d in dates) or 'latest' in dates or dates[0] >= dates[1]):
        raise LookupError('Choose two historical dates in chronological order.')
    snapshots = [capture_snapshot(engine, text, requested, progress) for requested in dates]
    data = {'schemaVersion': SCHEMA, 'createdAt': datetime.now(timezone.utc).isoformat(),
            'inputs': [i['input'] for i in items], 'tool': tool_version(), 'snapshots': snapshots}
    progress('Packaging evidence and checking offline replay')
    view = inspect(data)
    data['comparison'] = view['comparison']
    view['comparisonReplay'] = 'match'
    archive = pack(data)
    return view, archive


def pack(data):
    payload = encode(data)
    summary = ('Múcaro | BGP Routing Exposure Lookup\nInvestigation bundle v1\n\n'
               + 'Created: ' + data['createdAt'] + '\nInputs: ' + ', '.join(data['inputs']) + '\nDates: '
               + ', '.join(s['requestedDate'] for s in data['snapshots']) + '\n\n' + LIMITATION
               + '\n\nA newly observed adjacency is not proof of a new connection. Not seen is not proof of removal. '
               'There is no continuous monitoring between snapshots.\n'
               'Open this ZIP with Open investigation in the local app. No external queries are made. '
               'Raw RIS responses are base64-encoded under snapshots/evidence/risBase64 in investigation.json. '
               'CAIDA references and checksums are in each result.\n').encode()
    manifest = encode({'format': 'mucaro-routing-investigation', 'schemaVersion': SCHEMA,
                       'files': {name: {'sha256': digest(value), 'bytes': len(value)} for name, value in
                                 [('investigation.json', payload), ('SUMMARY.txt', summary)]}})
    if sum(map(len, (payload, summary, manifest))) > MAX_EXPANDED:
        raise LookupError('Investigation exceeds the bundle limit; narrow the query.')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, value in [('manifest.json', manifest), ('investigation.json', payload), ('SUMMARY.txt', summary)]:
            archive.writestr(name, value)
    value = buffer.getvalue()
    if len(value) > MAX_BUNDLE:
        raise LookupError('Investigation exceeds the 32 MB ZIP limit; narrow the query.')
    return value


def validate(data):
    if not isinstance(data, dict) or data.get('schemaVersion') != SCHEMA:
        raise LookupError('Unsupported investigation schema version.')
    if not isinstance(data.get('createdAt'), str) or not isinstance(data.get('tool'), dict):
        raise LookupError('Invalid investigation metadata.')
    inputs = data.get('inputs')
    if not isinstance(inputs, list) or not 1 <= len(inputs) <= MAX_PATH_INPUTS or any(not isinstance(i, str) or len(i) > 262144 for i in inputs):
        raise LookupError('Invalid investigation inputs.')
    snapshots = data.get('snapshots')
    if not isinstance(snapshots, list) or len(snapshots) not in (1, 2):
        raise LookupError('Invalid snapshot count.')
    for snapshot in snapshots:
        requested = snapshot['requestedDate']
        if not isinstance(requested, str):
            raise LookupError('Invalid observation date.')
        result, records = snapshot['result'], snapshot['evidence']
        if result['kind'] != 'paths' or len(result['results']) != len(inputs) or len(records) != len(inputs):
            raise LookupError('Snapshot inputs and evidence do not match.')
        for source_input, saved, record in zip(inputs, result['results'], records):
            if saved['input'] != source_input or record['input'] != source_input:
                raise LookupError('Snapshot inputs and evidence do not match.')
            if saved['status'] not in ('mapped', 'not_observed', 'error', 'invalid', 'special_use'):
                raise LookupError('Invalid saved result status.')
            if not isinstance(saved.get('groups'), list) or not isinstance(saved.get('asns'), dict) or not isinstance(saved.get('warnings'), list):
                raise LookupError('Invalid saved result.')
            for field in ('observation', 'organizations', 'relationships'):
                source = saved.get(field)
                if source is not None and (not isinstance(source, dict) or any(not isinstance(value, str) and value is not None for value in source.values())):
                    raise LookupError('Invalid source metadata.')
            if 'observation' in saved and not isinstance(saved['observation'].get('observedAt'), str):
                raise LookupError('Invalid observation timestamp.')
            if any(not isinstance(w, str) for w in saved['warnings']):
                raise LookupError('Invalid saved warnings.')
            # Rendering receives locally rebuilt groups for all successful captures.
            if not isinstance(record['organizations'], dict) or not isinstance(record['relationships'], list):
                raise LookupError('Invalid enrichment evidence.')
            for a, b, kind in record['relationships']:
                if type(a) is not int or type(b) is not int or not 1 <= a <= 4294967295 or not 1 <= b <= 4294967295 or kind not in ('provider', 'peer', 'customer', 'unknown'):
                    raise LookupError('Invalid relationship evidence.')
            for key, org in record['organizations'].items():
                if not key.isdigit() or not isinstance(org, dict) or not 1 <= int(key) <= 4294967295:
                    raise LookupError('Invalid organization evidence.')
                if any(value is not None and not isinstance(value, str) for field, value in org.items() if field in ('name', 'asName')):
                    raise LookupError('Invalid organization name.')
            if record['risBase64'] is not None:
                raw = base64.b64decode(record['risBase64'], validate=True)
                if len(raw) > 12_000_000:
                    raise LookupError('Routing response exceeds size limit.')
                response = json.loads(raw)
                if response.get('status') != 'ok' or not isinstance(response['data']['timestamp'], str):
                    raise LookupError('Invalid routing response.')
                timestamp = response['data']['timestamp']
                observed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                if requested != 'latest' and observed.date().isoformat() != requested:
                    raise LookupError('Routing observation date differs from requested date.')
                if saved['status'] in ('mapped', 'not_observed') and saved.get('observation', {}).get('observedAt') != timestamp:
                    raise LookupError('Saved observation timestamp differs from raw evidence.')
            elif saved['status'] in ('mapped', 'not_observed'):
                raise LookupError('Successful snapshot is missing raw evidence.')
    if len(snapshots) == 2 and ('latest' in [s['requestedDate'] for s in snapshots] or snapshots[0]['requestedDate'] >= snapshots[1]['requestedDate']):
        raise LookupError('Comparison dates must be chronological historical dates.')


def unpack(raw):
    if len(raw) > MAX_BUNDLE:
        raise LookupError('Investigation ZIP exceeds 32 MB.')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            if len(infos) != 3 or {i.filename for i in infos} != FILES:
                raise LookupError('Unexpected or duplicate ZIP members. Open a version 1 investigation bundle.')
            if sum(i.file_size for i in infos) > MAX_EXPANDED or any(i.flag_bits & 1 or i.is_dir() or i.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) for i in infos):
                raise LookupError('Unsupported or oversized ZIP members.')
            contents = {i.filename: archive.read(i) for i in infos}
        manifest = json.loads(contents['manifest.json'])
        if manifest.get('format') != 'mucaro-routing-investigation' or manifest.get('schemaVersion') != SCHEMA:
            raise LookupError('Unsupported investigation format or version.')
        for name in ('investigation.json', 'SUMMARY.txt'):
            if manifest['files'][name] != {'sha256': digest(contents[name]), 'bytes': len(contents[name])}:
                raise LookupError('Bundle integrity check failed: content does not match its checksum.')
        data = json.loads(contents['investigation.json'])
        validate(data)
        # Detect corrupt saved groups while preserving evidence for mismatch reporting.
        inspected = inspect(data)
        for snapshot, checks in zip(inspected['snapshots'], inspected['replay']):
            for result, check in zip(snapshot['results'], checks):
                if check['status'] != 'match':
                    result['groups'], result['asns'] = [], {}
                    result['warnings'] = list(result['warnings']) + ['Saved result could not be reproduced; use the replay status for details.']
        return inspected
    except LookupError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError, RecursionError,
            zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise LookupError('Invalid or damaged investigation bundle.') from exc


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Inspect and replay a saved routing investigation offline.")
    parser.add_argument("bundle", type=Path, help="Version 1 investigation ZIP")
    args = parser.parse_args()
    try:
        if args.bundle.stat().st_size > MAX_BUNDLE:
            raise LookupError("Investigation ZIP exceeds 32 MB.")
        result = unpack(args.bundle.read_bytes())
        print(json.dumps(result, indent=2))
        if any(check['status'] == 'mismatch' for snapshot in result['replay'] for check in snapshot) or result['comparisonReplay'] == 'mismatch':
            raise SystemExit(1)
    except (LookupError, OSError) as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == '__main__':
    main()
