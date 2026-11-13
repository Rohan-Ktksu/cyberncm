"""Compare prepared windows without modifying them. Usage: python compare_windows.py OUT.json FILE [FILE ...]"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def load(path):
    with np.load(path, allow_pickle=False) as z:
        data = {k: z[k] for k in ('X', 'day', 'src', 't', 'family', 'features', 'family_names')}
    n = len(data['X'])
    if any(len(data[k]) != n for k in ('day', 'src', 't', 'family')):
        raise ValueError(f'Misaligned row arrays: {path}')
    keys = list(zip(data['day'].tolist(), data['src'].tolist(), data['t'].tolist()))
    if len(set(keys)) != n:
        raise ValueError(f'Duplicate day/source/time keys: {path}')
    if not np.isfinite(data['X']).all() or not np.isfinite(data['t']).all():
        raise ValueError(f'Non-finite data: {path}')
    return data, {key: i for i, key in enumerate(keys)}


def compare(paths):
    report = {'assumption': 'Source IDs must have the same meaning across files; counts alone cannot establish raw-data reproducibility.', 'files': [], 'comparisons': []}
    baseline, base_keys = load(paths[0])
    for path in paths:
        data, keys = load(path)
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        report['files'].append({'path': str(path), 'sha256': digest, 'windows': len(keys),
                                'per_day': {str(int(d)): int((data['day'] == d).sum()) for d in np.unique(data['day'])}})
        if path == paths[0]:
            continue
        if not np.array_equal(data['features'], baseline['features']):
            raise ValueError('Feature schemas differ; compare only matching preprocessing schemas')
        common = sorted(base_keys.keys() & keys.keys())
        left = np.array([base_keys[k] for k in common], dtype=int)
        right = np.array([keys[k] for k in common], dtype=int)
        a = baseline['X'][left]
        b = data['X'][right]
        old_labels = baseline['family_names'][baseline['family'][left]]
        new_labels = data['family_names'][data['family'][right]]
        report['comparisons'].append({'against': str(path), 'common_keys': len(common),
            'baseline_only_per_day': {str(int(d)): sum(k[0] == d for k in base_keys.keys() - keys.keys()) for d in np.unique(baseline['day'])},
            'candidate_only_per_day': {str(int(d)): sum(k[0] == d for k in keys.keys() - base_keys.keys()) for d in np.unique(data['day'])},
            'changed_labels_on_common_keys': int((old_labels != new_labels).sum()),
            'changed_feature_rows_exact': int(np.any(a != b, axis=1).sum()),
            'max_absolute_feature_difference': float(np.max(np.abs(a-b))) if len(common) else None})
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('files', nargs='+', type=Path)
    args = parser.parse_args()
    report = compare(args.files)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
