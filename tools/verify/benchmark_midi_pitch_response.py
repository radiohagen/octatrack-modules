#!/usr/bin/env python3
"""Compare active Harmony LIVE guest instructions in two frozen artifact trees.

Uses the integration's native Part/Follow fixture. The native MIDI enqueue
function is replaced by its packet recorder and excluded from instruction
counts. These are guest instructions, not hardware cycles, CPU percentages,
UART timing, or total sequencer cost. No build or artifact modification occurs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from unicorn import UC_HOOK_CODE
from unicorn.m68k_const import UC_M68K_REG_A2, UC_M68K_REG_D4, UC_M68K_REG_D7


RECEIVER = 1
RELEASE = 0x46c77a16 + RECEIVER * 32
OWNERS = 0x46c78152 + RECEIVER * 128
DEADLINE = 0x46c7a7f0 + RECEIVER * 4
ENQUEUE = 0x40010bc8


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def identity(root, remix):
    marker = (root / 'mainos_bus.remix').read_text().split()
    assert len(marker) == 2 and marker[0] == remix, ('wrong remix', marker, remix)
    files = ('mainos_bus.bin', 'mainos_bus.remix', 'platform/runtime/runtime.elf',
             'platform/runtime/runtime.bin', 'platform/layout.json')
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files}


def measure(m, action):
    instructions = 0
    enqueues = 0

    def trace(uc, pc, size, data):
        nonlocal instructions, enqueues
        if pc == ENQUEUE:
            enqueues += 1
        elif pc not in m.stops:
            instructions += 1

    hook = m.uc.hook_add(UC_HOOK_CODE, trace)
    try:
        action()
    finally:
        m.uc.hook_del(hook)
    assert instructions > 0
    return instructions, enqueues


def output(m, voices, events, scratch):
    actual_voices = [int.from_bytes(m.uc.mem_read(RELEASE + slot * 8 + 4, 4), 'big')
                     for slot in range(4)]
    assert actual_voices == list(voices) + [0xffffffff] * (4 - len(voices))
    owners = bytes(m.uc.mem_read(OWNERS, 128))
    expected_owners = bytearray(b'\xff' * 128)
    for slot, pitch in enumerate(voices):
        expected_owners[pitch] = RECEIVER * 4 + slot
    assert owners == expected_owners
    deadline = int.from_bytes(m.uc.mem_read(DEADLINE, 4), 'big')
    assert deadline == 37
    assert m.events == events, (m.events, events)
    return dict(voices=actual_voices, owners=owners.hex(), deadline=deadline,
                events=list(m.events), scratch=list(scratch))


def benchmark(root, remix, machine, response):
    before = identity(root, remix)
    rows = subprocess.check_output(
        ['m68k-elf-nm', str(root / 'platform/runtime/runtime.elf')], text=True)
    symbols = {fields[2]: int(fields[0], 16) for row in rows.splitlines()
               if len(fields := row.split()) == 3}
    for name in ('mh_follow_shift', 'bf_response_tick', 'bf_response_adjust', 'ms_snap'):
        assert name in symbols, ('missing required combined symbol', name)
    cases = {}
    for scale, key, chord in (('major', 1, (36, 40, 43)),
                              ('dorian', machine.raw_scale(0, 1), (36, 39, 43))):
        for mode in (1, 2):
            tones = chord[:1] if mode == 1 else chord
            targets = (38,) if mode == 1 else (38, 41, 45)
            factory = lambda: machine.Machine(lambda: symbols.copy(), artifact_root=root)
            with patch.object(response, 'Machine', factory):
                m = response.fixture(pitches=tones)
            m.uc.mem_write(m.part_address(0, 5), b'\0')
            m.uc.mem_write(m.part_address(RECEIVER, 5), bytes((mode,)))
            m.set_key(0, key)
            m.set_key(RECEIVER, 24)  # own KEY differs from inherited source KEY
            m.uc.mem_write(symbols['ch_sequence_quality'] + RECEIVER, b'\0')
            m.call('bf_response_tick', 1 << RECEIVER, 0)
            m.uc.mem_write(m.scratch, b'\x24')
            m.call('bf_response_observe', regs={UC_M68K_REG_D7: RECEIVER,
                   UC_M68K_REG_D4: 0, UC_M68K_REG_A2: m.scratch})

            def record(stage, action, voices, events, scratch):
                m.events.clear()
                instructions, enqueues = measure(m, action)
                result = output(m, voices, events, scratch)
                assert enqueues == len(events)
                inputs = dict(stage=stage, source_mode=0, receiver_mode=mode, key=key,
                              quality=0, original_voices=tones, old_root=36,
                              new_root=36 if stage == 'unchanged' else 38)
                name = f'{scale}.{"note" if mode == 1 else "chord"}.{stage}'
                cases[name] = dict(instructions=instructions, enqueue_calls=enqueues,
                                   inputs=inputs, input_hash=digest(inputs),
                                   outputs=result, output_hash=digest(result))

            record('unchanged', lambda: m.call('bf_response_tick'), tones, [], [])
            m.uc.mem_write(symbols['bf_roots'], b'\x26')
            m.uc.mem_write(symbols['bf_pitches'], b'\x3e')
            packets = ([(0x91, pitch, 0) for pitch in tones] +
                       [(0x91, pitch, 91) for pitch in targets])
            record('moved', lambda: m.call('bf_response_tick'), targets, packets, [])
            scratch = []

            def arp():
                for pitch, target in zip(tones, targets):
                    m.uc.mem_write(m.scratch, bytes((pitch,)))
                    m.call('bf_response_adjust', regs={UC_M68K_REG_D7: RECEIVER,
                           UC_M68K_REG_A2: m.scratch})
                    value = m.uc.mem_read(m.scratch, 1)[0]
                    assert value == target, (scale, mode, pitch, value, target)
                    scratch.append(value)

            record('cached_arp', arp, targets, [], scratch)
    assert identity(root, remix) == before, 'frozen artifacts changed during measurement'
    return dict(artifacts=before, pitch_provider='mh_pitch_shift' in symbols, cases=cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--integration-root', required=True, type=Path)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--remix', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.integration_root.resolve() / 'tools/verify'))
    import midi_machine
    import verify_midi_follow_response
    baseline = benchmark(args.baseline.resolve(), args.remix,
                         midi_machine, verify_midi_follow_response)
    candidate = benchmark(args.candidate.resolve(), args.remix,
                          midi_machine, verify_midi_follow_response)
    assert baseline['cases'].keys() == candidate['cases'].keys()
    comparisons = {}
    for name, result in candidate['cases'].items():
        old = baseline['cases'][name]
        assert result['input_hash'] == old['input_hash'], ('changed inputs', name)
        assert result['output_hash'] == old['output_hash'], ('changed outputs', name)
        change = 100 * (result['instructions'] / old['instructions'] - 1)
        comparisons[name] = dict(baseline=old['instructions'], candidate=result['instructions'],
                                 change_percent=change)
        print(f'{name}: {old["instructions"]} -> {result["instructions"]} ({change:+.2f}%)')
    receipt = dict(boundary=__doc__, remix=args.remix, baseline=baseline, candidate=candidate,
                   comparisons=comparisons,
                   maximum_regression_percent=max(c['change_percent'] for c in comparisons.values()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(f'[ok] {len(comparisons)} matched instruction cases; {args.output}')


if __name__ == '__main__':
    main()
