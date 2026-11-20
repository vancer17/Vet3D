"""Pure whole-ring and evidence checks. Review content remains an explicit human/agent judgment."""
import math
from motion import offsets, adjacent_overlap, stop_travel_limits


def positive(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError('expected a positive finite number')
    return value


def ring_edges(count):
    if isinstance(count, bool) or not isinstance(count, int) or count < 3:
        raise ValueError('retention requires at least three ordered petals')
    return {tuple(sorted((i+1, (i+1) % count+1))) for i in range(count)}


def pair(value, count):
    if len(value) != 2 or any(isinstance(i, bool) or not isinstance(i, int) or not 1 <= i <= count for i in value) or value[0] == value[1]:
        raise ValueError('invalid interface pair')
    return tuple(sorted(value))


def connection_report(count, interfaces):
    """Check every ring edge, duplicates and graph connectivity; infer no physical capture."""
    expected = ring_edges(count)
    edges = [pair([s['owner'], s['receiver']], count) for s in interfaces]
    unique = set(edges)
    remaining, components = set(range(1, count+1)), []
    while remaining:
        reached, pending = set(), [min(remaining)]
        while pending:
            node = pending.pop()
            if node in reached:
                continue
            reached.add(node)
            pending.extend(b if a == node else a for a, b in unique if node in (a, b))
        remaining -= reached
        components.append(sorted(reached))
    missing, extra = sorted(expected-unique), sorted(unique-expected)
    duplicates = sorted(e for e in unique if edges.count(e) > 1)
    return {'components': components, 'missing_ring_edges': missing, 'unexpected_edges': extra,
            'duplicate_edges': duplicates,
            'complete': len(components) == 1 and not (missing or extra or duplicates)}


def motion_cases(cases, count):
    if not cases:
        raise ValueError('declare every retained motion before acceptance')
    keys = []
    for case in cases:
        key = (case['mode'], positive(case['travel_mm']))
        offsets(count, key[1], key[0])
        if key in keys:
            raise ValueError('duplicate retained motion')
        keys.append(key)
    return keys


def require_stops(manifest):
    """Require complete ring metadata and a declared, reachable motion set."""
    stops = manifest.get('axial_stops') or {}
    if stops.get('assembly_method') != 'print_in_place':
        raise ValueError('default retention requires integral stops and the implemented print_in_place branch')
    graph = connection_report(manifest['count'], stops.get('interfaces', []))
    if not graph['complete']:
        raise ValueError(f'incomplete whole-ring stop connection: {graph}')
    for mode, travel in motion_cases(stops.get('retained_motions'), manifest['count']):
        ranges = stop_travel_limits(offsets(manifest['count'], travel, mode), stops['interfaces'])
        if any(not r['within_limits'] for r in ranges):
            raise ValueError('a retained motion exceeds a stop limit')
    return graph


def check_contacts(report, manifest, assembly_hash):
    """Require both directions and all three actual endpoint samples for every interface."""
    if report['assembly_sha256'] != assembly_hash or report['all_passed'] is not True:
        raise ValueError('stale or failed stop contact report')
    probe = positive(report['contact_probe_mm'])
    tolerance = report['overlap_tolerance_mm3']
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('invalid contact tolerance')
    expected = {(s['owner'], s['receiver'], side): s for s in manifest['axial_stops']['interfaces']
                for side in ('negative', 'positive')}
    attached = set()
    for row in report['attachments']:
        key = (row['owner'], row['receiver'])
        if (*key, 'positive') not in expected or key in attached:
            raise ValueError('duplicate or unexpected tongue attachment')
        attached.add(key)
        positive(row['root_overlap_mm3'])
        positive(row['receiver_bearing_volume_mm3'])
    if attached != {(a, b) for a, b, _ in expected}:
        raise ValueError('missing tongue root or bearing evidence')
    seen = set()
    for row in report['contacts']:
        key = (row['owner'], row['receiver'], row['direction'])
        if key not in expected or key in seen or row['passed'] is not True:
            raise ValueError('missing, duplicate, unexpected or failed contact direction')
        seen.add(key)
        limit = positive(expected[key][key[2]+'_travel_mm'])
        if probe >= limit or len(row['states']) != 3:
            raise ValueError('invalid endpoint probes')
        sign = -1 if key[2] == 'negative' else 1
        for sample, name, delta in zip(row['states'], ('before', 'contact', 'overtravel'), (-probe, 0, probe)):
            volume = sample['overlap_mm3']
            if sample['state'] != name or not math.isclose(sample['relative_offset_mm'], sign*(limit+delta), abs_tol=1e-9):
                raise ValueError('contact sample is not at its declared endpoint')
            if not math.isfinite(volume) or volume < 0 or (volume > tolerance) != (name == 'overtravel'):
                raise ValueError('endpoint evidence does not demonstrate an axial barrier')
    if seen != set(expected):
        raise ValueError('contact evidence omits interfaces or directions')


def check_motion(report, manifest, assembly_hash, mode, travel, intervals, interval_hash):
    """Audit report coverage and recompute kinematics/overlap; collision volumes are reported evidence."""
    n = manifest['count']
    positions = offsets(n, travel, mode)
    if report['schema'] != 'twisty.validation.v1' or report.get('purpose') != 'retention_motion':
        raise ValueError('study-only or unsupported report cannot qualify for acceptance')
    if report['assembly_sha256'] != assembly_hash or report['part_sha256'] != [p['sha256'] for p in manifest['parts']]:
        raise ValueError('motion evidence belongs to different final parts')
    if (report['mode'], report['travel_mm']) != (mode, travel) or report['offsets_mm'] != positions:
        raise ValueError('motion evidence does not match the retained motion')
    ranges = stop_travel_limits(positions, manifest['axial_stops']['interfaces'])
    overlap = adjacent_overlap(intervals, positions)
    if report['stop_travel_limits'] != ranges or any(not r['within_limits'] for r in ranges):
        raise ValueError('missing or exceeded stop ranges')
    if report['rail_interval_source']['sha256'] != interval_hash or report['rail_overlap'] != overlap or any(r['overlap_mm'] <= 0 for r in overlap):
        raise ValueError('missing, stale or disengaged capture intervals')
    states = report['states']
    progress = [s['progress'] for s in states]
    if len(progress) < 3 or progress[0] != 0 or progress[-1] != 1 or any(not math.isfinite(x) for x in progress) or any(a >= b for a, b in zip(progress, progress[1:])):
        raise ValueError('motion evidence needs ordered closed, intermediate and open samples')
    tolerance = report['overlap_tolerance_mm3']
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('invalid motion tolerance')
    pairs = n*(n-1)//2
    if report['sampled_collision_free'] is not True or report['pair_check_total'] != pairs*len(states):
        raise ValueError('failed or incomplete full-pair collision evidence')
    for state in states:
        volume = state['max_overlap_mm3']
        if state['pair_checks'] != pairs or state['collisions'] or not math.isfinite(volume) or not 0 <= volume <= tolerance:
            raise ValueError('collision or incomplete pair coverage')


def check_review(review, verify_file):
    """Require an attributable review and nonempty hash-bound artifacts; do not infer their meaning."""
    if review['status'] != 'passed' or any(not isinstance(review.get(k), str) or not review[k].strip() for k in ('reviewer', 'findings')):
        raise ValueError('review is missing, pending, failed or unattributed')
    if not review.get('artifacts'):
        raise ValueError('review has no actual evidence files')
    for ref in review['artifacts']:
        verify_file(ref)


def check_interface_reviews(rows, count, kind):
    expected, seen = ring_edges(count), set()
    for row in rows:
        edge = pair(row['parts'], count)
        if edge not in expected or edge in seen:
            raise ValueError('duplicate or unexpected reviewed interface')
        seen.add(edge)
        if kind == 'capture' and row['captured'] is not True:
            raise ValueError('radial capture review failed')
        if kind == 'walls' and positive(row['minimum_mm']) < positive(row['required_mm']):
            raise ValueError('measured wall thickness is below the task requirement')
    if seen != expected:
        raise ValueError('interface reviews omit part of the ring')


def check_fit_review(review, count):
    """Require all interfaces and declared measured gap range; calibration is explicit."""
    if review['process_status'] not in ('assumed', 'calibrated') or not review['basis'].strip():
        raise ValueError('fit process status and basis required')
    if not review.get('coupon_artifacts'):
        raise ValueError('actual mating-rail coupon evidence required')
    expected, seen = ring_edges(count), set()
    for row in review['interfaces']:
        edge = pair(row['parts'], count)
        if edge not in expected or edge in seen:
            raise ValueError('unexpected or duplicate fit interface')
        seen.add(edge)
        lo, hi = positive(row['minimum_gap_mm']), positive(row['maximum_gap_mm'])
        lower, upper = map(positive, row['required_range_mm'])
        if not lower <= lo <= hi <= upper:
            raise ValueError('running clearance outside the declared process range')
    if seen != expected:
        raise ValueError('fit review omits interfaces')


def check_reimport(report, manifest, assembly_hash, mode, travel, glb_hash):
    if report['passed'] is not True or report['assembly_sha256'] != assembly_hash or report.get('glb_sha256') != glb_hash or (report['mode'], report['travel_mm']) != (mode, travel):
        raise ValueError('failed, stale or unbound animation reimport')
    frames = report.get('sample_frames', [])
    if len(frames) < 3 or any(isinstance(f, bool) or not isinstance(f, int) or f < 1 for f in frames) or frames != sorted(set(frames)):
        raise ValueError('missing reimport sample frames')
    expected = {(frame, f'Petal_{i:03d}') for frame in frames for i in range(1, manifest['count']+1)}
    seen = set()
    for row in report['checks']:
        key = (row['frame'], row['part'])
        if key not in expected or key in seen:
            raise ValueError('duplicate or unexpected animation sample')
        seen.add(key)
        for name, bound in [('position_error_mm', .01), ('rotation_error_deg', .1), ('screw_error_deg', .1)]:
            if not math.isfinite(row[name]) or not 0 <= row[name] < bound:
                raise ValueError('animation transform evidence failed')
    if seen != expected:
        raise ValueError('animation reimport omits frames or petals')


def check_evidence(manifest, assembly_hash, bundle, read_artifact, verify_file):
    """Combine required reports/reviews. Adapters verify file hashes before reading them."""
    graph = require_stops(manifest)
    if bundle['schema'] != 'twisty.evidence.v1' or bundle['assembly_sha256'] != assembly_hash:
        raise ValueError('evidence bundle does not bind the final assembly')
    check_contacts(read_artifact(bundle['stop_contacts']), manifest, assembly_hash)
    intervals = read_artifact(bundle['intervals'])
    if intervals['assembly_sha256'] != assembly_hash:
        raise ValueError('capture intervals measured for a different assembly')
    from capture import check_capture
    numeric_capture = check_capture(read_artifact(bundle['capture_measurement']), manifest,
                                    assembly_hash, intervals['intervals_mm'])
    cases = motion_cases(manifest['axial_stops']['retained_motions'], manifest['count'])
    supplied = motion_cases(bundle['motions'], manifest['count'])
    if set(cases) != set(supplied):
        raise ValueError('evidence must cover exactly every declared retained motion')
    for case in bundle['motions']:
        mode, travel = case['mode'], case['travel_mm']
        check_motion(read_artifact(case['validation']), manifest, assembly_hash, mode, travel,
                     intervals['intervals_mm'], bundle['intervals']['sha256'])
        verify_file(case['glb'])
        check_reimport(read_artifact(case['reimport']), manifest, assembly_hash, mode, travel, case['glb']['sha256'])
        check_review(case['visual_review'], verify_file)
    reviews = bundle['reviews']
    for kind in ('capture', 'walls', 'sections', 'assembly', 'fit'):
        check_review(reviews[kind], verify_file)
    check_fit_review(reviews['fit'], manifest['count'])
    for ref in reviews['fit']['coupon_artifacts']:
        verify_file(ref)
    for kind in ('capture', 'walls'):
        check_interface_reviews(reviews[kind]['interfaces'], manifest['count'], kind)
    if reviews['assembly']['method'] != manifest['axial_stops']['assembly_method']:
        raise ValueError('assembly review uses a different manufacturing branch')
    return {'connection': graph, 'numeric_capture': numeric_capture,
            'retained_motions': manifest['axial_stops']['retained_motions'],
            'scope': 'Complete bound digital evidence, including attributed capture/wall/assembly/visual reviews. '
                     'Not independent verification of review content, continuous motion, FDM feasibility or physical strength.'}
