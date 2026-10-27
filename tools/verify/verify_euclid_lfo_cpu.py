#!/usr/bin/env python3
"""Profile the already-built Euclid LFO image; never rebuild firmware.

Run in the Octabam integration after make bus. Reuses the focused native probe
and rebuilds only its host executable when necessary. Each run freezes the
image, linked runtime, symbols and hashes in a unique ignored output directory.
Executed instruction/division counts are not hardware cycles or headroom.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile

KEY = ('kind', 'pattern', 'mode', 'midi', 'stage')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(profile, baseline):
    """Require the same test inputs and observable output for every case."""
    key = lambda case: tuple(case[field] for field in KEY)
    expected = {key(case): case for case in baseline['cases']}
    actual = {key(case): case for case in profile['cases']}
    assert len(expected) == len(baseline['cases']) and len(actual) == len(profile['cases']), 'duplicate CPU profile cases'
    assert expected.keys() == actual.keys(), 'CPU profile scenario set changed'
    assert all('input_hash' in case for case in profile['cases']+baseline['cases']), \
        'CPU profile lacks input hashes; regenerate the baseline using its frozen binaries and the current probe'
    changed_inputs = [k for k, case in actual.items()
                      if (case['calls'], case['input_hash']) !=
                      (expected[k]['calls'], expected[k]['input_hash'])]
    assert not changed_inputs, f'CPU profile inputs changed: {changed_inputs[:5]}'
    mismatches = [k for k, case in actual.items()
                  if (case['calls'], case['output_hash']) !=
                  (expected[k]['calls'], expected[k]['output_hash'])]
    assert not mismatches, f'CPU profile observable output changed: {mismatches[:5]}'
    return expected


def summarize(profile, baseline=None):
    expected = compare(profile, baseline) if baseline else None
    groups = defaultdict(lambda: dict(cases=0, calls=0, instructions=0, long_divisions=0,
                                      peak=0, baseline_instructions=0, baseline_long_divisions=0))
    for case in profile['cases']:
        group = groups[(case['kind'], case['stage'])]
        group['cases'] += 1
        for field in ('calls', 'instructions', 'long_divisions'):
            group[field] += case[field]
        group['peak'] = max(group['peak'], case['peak'])
        if expected:
            old = expected[tuple(case[field] for field in KEY)]
            for field in ('instructions', 'long_divisions'):
                group['baseline_' + field] += old[field]
    result = []
    for (kind, stage), group in groups.items():
        if expected:
            old = group['baseline_instructions']
            group['instruction_change_percent'] = 100 * (group['instructions'] - old) / old
        else:
            del group['baseline_instructions'], group['baseline_long_divisions']
        result.append(dict(kind=kind, stage=stage, **group))
    return result


def main():
    # Keep pure receipt comparison importable in the source-only repository;
    # only executing the integration runner requires Octabam's toolpath setup.
    from verify_euclid_lfo import ROOT, run
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', type=Path, help='earlier cpu-profile.json; reject output mismatches')
    args = ap.parse_args()
    inputs = {'mainos.bin': ROOT/'out/mainos_bus.bin',
              'runtime.raw': ROOT/'out/platform/runtime.raw',
              'runtime.elf': ROOT/'out/platform/runtime/runtime.elf',
              'layout.json': ROOT/'out/platform/layout.json'}
    for path in inputs.values():
        if not path.is_file(): ap.error(f'{path} missing; build the intended remix in Octabam first')
    parent = ROOT/'out/euclid-lfo-cpu'
    parent.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='profile-', dir=parent))
    hashes = {name: digest(path) for name, path in inputs.items()}
    for name, path in inputs.items(): shutil.copy2(path, out/name)
    assert all(digest(path) == digest(out/name) == hashes[name] for name, path in inputs.items()), \
        'Build outputs changed while snapshotting; do not build concurrently with this profile'
    symbols = {fields[2]: int(fields[0], 16)
               for line in run(['m68k-elf-nm', out/'runtime.elf']).splitlines()
               if len(fields := line.split()) == 3}
    (out/'symbols.txt').write_text(''.join(f'{name} {value:x}\n' for name, value in symbols.items()))
    layout = json.loads((out/'layout.json').read_text())
    image = (out/'mainos.bin').read_bytes()
    for table, symbol in ((0x400d6210, 'eul_audio'), (0x400d6290, 'eul_midi')):
        assert struct.unpack_from('>I', image, table + 19*4 - 0x40000400)[0] == symbols[symbol], \
            'Image waveform dispatch does not match the linked runtime symbols'
    if not (ROOT/'out/emu/CMakeCache.txt').is_file():
        run(['cmake', '-S', 'tools/emu/ot_emu', '-B', 'out/emu'])
    (out/'probe-build.log').write_text(run(['cmake', '--build', 'out/emu', '--target', 'ot_euclid_lfo_test', '-j8']))
    probe = ROOT/'out/emu/ot_euclid_lfo_test'
    result = run([probe, out/'mainos.bin', out/'runtime.raw', f'{layout["base"]:x}',
                  f'{symbols["eul_bank"]:x}', out, f'{symbols["eul_file_encode"]:x}',
                  f'{symbols["eul_file_decode"]:x}', '--cpu-only'])
    (out/'probe.log').write_text(result)
    profile = json.loads((out/'cpu-profile.json').read_text())
    baseline = json.loads(args.baseline.read_text()) if args.baseline else None
    summary = summarize(profile, baseline)
    source_paths = ('modules/euclid-lfo/engine.c', 'modules/euclid-lfo/engine.h',
                    'modules/euclid-lfo/runtime.c', 'modules/euclid-lfo/control.s',
                    'modules/euclid-lfo/control-sidecar.s', 'modules/euclid-lfo/probe.cpp',
                    'tools/verify/verify_euclid_lfo.py', 'tools/verify/verify_euclid_lfo_cpu.py')
    status = run(['git', 'status', '--porcelain']).splitlines()
    verifier_checkout = dict(commit=run(['git', 'rev-parse', 'HEAD']).strip(),
                             dirty=bool(status), status=status,
                             source_sha256={path: digest(ROOT/path) for path in source_paths})
    receipt = dict(hardware_cycles=False, verifier_checkout=verifier_checkout,
                   loaded_artifact_source='Not inferred from the current verifier checkout. Input hashes identify the exact binaries; retain their independent build/source receipt.',
                   input_sha256=hashes, probe_sha256=digest(probe),
                   profile_sha256=digest(out/'cpu-profile.json'), cases=len(profile['cases']),
                   baseline_sha256=digest(args.baseline) if args.baseline else None,
                   matched_input_hashes=len(profile['cases']) if baseline else None,
                   matched_output_hashes=len(profile['cases']) if baseline else None,
                   summary=summary,
                   limits='Executed ColdFire instructions, not hardware cycles. Group totals weight the fixed test matrix, not a measured real-world workload. Output hashes supplement, not replace, the full equivalence/native gates.')
    (out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(f'PASS: {len(profile["cases"])} linked CPU scenarios' +
          ('; all observable output hashes match baseline' if baseline else ''))
    for group in summary:
        change = f' ({group["instruction_change_percent"]:+.1f}%)' if baseline else ''
        print(f'{group["kind"]:8} {group["stage"]:10}: {group["instructions"]:9} instructions{change}; '
              f'{group["long_divisions"]:7} long divisions; peak {group["peak"]}')
    print(f'Receipt: {out/"receipt.json"}')


if __name__ == '__main__':
    main()
