#!/usr/bin/env python3
"""Compare linked Harmony pitch/voice/ACC behavior across two firmware builds.

Use the Octabam integration's Python environment and pass --integration when
running this author-repository copy. Images remain local, outside source.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--integration', type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--candidate', type=Path, required=True)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--section', choices=('all', 'accumulator'), default='all',
                    help='Rerun only accumulator behavior after an isolated phase change.')
    args = ap.parse_args()
    sys.path.insert(0, str(args.integration / 'tools/verify'))
    from midi_machine import Machine, MODES, raw_scale
    from unicorn import UC_HOOK_CODE
    from unicorn.m68k_const import UC_M68K_REG_D2, UC_M68K_REG_D6

    class Linked(Machine):
        def __init__(self, artifacts):
            raw = subprocess.check_output(
                ['m68k-elf-nm', str(artifacts / 'platform/runtime/runtime.elf')], text=True)
            symbols = {name: int(address, 16) for address, name in
                       re.findall(r'^([0-9a-f]+) [TtBbDdAa] ([\w.]+)$', raw, re.M)}
            super().__init__(lambda: symbols, artifact_root=artifacts)
            self.call('store_part_activate', stop=0x4000f938)

        def c(self, name, *values):
            self.uc.mem_write(self.stack + 4, b''.join(
                (value & 0xffffffff).to_bytes(4, 'big') for value in values))
            return self.call(name)

        def configure(self, kind, key, mode=0):
            # Arithmetic fixtures configure native fields without the bank
            # transition work that the lifecycle gates exercise separately.
            self.uc.mem_write(self.part_address(0, 5), bytes((kind,)))
            self.set_key(0, raw_scale(key, mode) if key >= 0 else 0)

        def generate(self, note, transpose=0):
            self.uc.mem_write(self.scratch, bytes((note, 11, 12, 13)))
            status = self.call('mh_generate', 0, transpose & 0xffffffff, a0=self.scratch)
            return status, bytes(self.uc.mem_read(self.scratch, 4))

    machines = [Linked(args.baseline), Linked(args.candidate)]
    counts = dict(quantization=0, note_generation=0, spread=0, voicing=0, fixed_size=0,
                  accumulator=0, accumulator_locks=0, accumulator_reset=0,
                  accumulator_invalid_arguments=0)
    scoring = [0, 0]
    for index, m in enumerate(machines):
        def score_hit(u, pc, size, data, index=index):
            scoring[index] += 1
        address = m.sym['.voice_score']
        m.uc.hook_add(UC_HOOK_CODE, score_hit, begin=address, end=address)

    def same(name, values, case):
        assert values[0] == values[1], (name, case, values)
        counts[name] += 1
        return values[0]

    if args.section == 'all':
        modes = range(7) if 'ms_decode' in machines[0].sym else (0, 5)
        for mode in modes:
            for key in range(12):
                for m in machines:
                    m.configure(1, key, mode)
                degrees = [p for p in range(128) if (p-key) % 12 in MODES[mode]]
                for pitch in range(128):
                    expected = min(degrees, key=lambda p: (abs(p-pitch), p))
                    result = same('quantization', [m.call('mh_quant_at', pitch, 0,
                        regs={UC_M68K_REG_D2: 0}) for m in machines], (mode, key, pitch))
                    assert result == expected, (mode, key, pitch, result, expected)
                    result = same('note_generation', [m.generate(pitch) for m in machines],
                                  (mode, key, pitch))
                    assert result == (1, bytes((expected,))*4)
        for kind in (0, 1, 2):
            for key in (-1, 0):
                for m in machines:
                    m.configure(kind, key)
                for pitch in (0, 1, 11, 12, 60, 126, 127, 128, 255):
                    same('quantization', [m.call('mh_quant_at', pitch, 0,
                         regs={UC_M68K_REG_D2: 0}) for m in machines], (kind, key, pitch))
                    for transpose in (-64, -12, -1, 0, 1, 12, 63):
                        same('note_generation', [m.generate(pitch, transpose) for m in machines],
                             (kind, key, pitch, transpose))
        print('[ok] all scale/key/pitch quantization and NOTE generation; OFF and bounds', flush=True)

        # The helper's documented input is sorted. Include duplicate pitches,
        # wide intervals, triad padding and atomic failures at the MIDI ceiling.
        for count in (3, 4):
            for base in range(128):
                for intervals in ((0, 0, 0), (1, 2, 3), (4, 7, 14), (12, 14, 26), (11, 22, 33)):
                    pitches = [base, *(base+i for i in intervals)][:count]
                    if max(pitches) > 127:
                        continue
                    initial = bytes(pitches + ([255] if count == 3 else []))
                    for spread in range(3):
                        results = []
                        for m in machines:
                            m.uc.mem_write(m.scratch, initial)
                            status = m.call('mh_spread', spread, a0=m.scratch,
                                            regs={UC_M68K_REG_D6: count})
                            results.append((status, bytes(m.uc.mem_read(m.scratch, 4))))
                        result = same('spread', results, (count, initial, spread))
                        wanted = list(pitches)
                        if spread == 1:
                            wanted[1] += 12
                        elif spread == 2:
                            wanted[1:] = [p+12 for p in wanted[1:]]
                        if max(wanted) > 127:
                            assert result == (0, initial)
                        else:
                            assert result == (1, bytes(sorted(wanted) + ([255] if count == 3 else [])))
        print('[ok] sorted spread helper: CLOSE/OPEN/WIDE, duplicate tones, ceilings and padding', flush=True)

        progression = (0, 1, 10, 11, 12, 24, 47, 48, 59, 60, 60, 61, 62, 65,
                       67, 72, 60, 84, 115, 116, 120, 126, 127)
        for quality in range(8):
            for spread in range(3):
                for voic in range(5):
                    for root_mode in range(4):
                        for m in machines:
                            m.configure(2, quality % 12, (quality % 7) if len(tuple(modes)) == 7 else 0)
                            m.call('mh_voice_clear')
                            for setting, value in (('voic', voic), ('sprd', spread),
                                                   ('size', 0), ('root', root_mode)):
                                m.call('mh_'+setting+'_set', 0, value)
                            m.uc.mem_write(m.sym['ch_current'], bytes((quality,)))
                        for pitch in progression:
                            results = []
                            for m in machines:
                                generated = m.generate(pitch)
                                m.call('mh_voice_at', 0, 0, a0=m.scratch)
                                results.append((generated, bytes(m.uc.mem_read(m.scratch, 4)),
                                                bytes(m.uc.mem_read(m.sym['mh_voice_history'], 8))))
                            same('voicing', results, (quality, spread, voic, pitch, root_mode))
        assert all(scoring), ('AUTO scoring must execute under stable settings', scoring)
        print('[ok] all natural chord recipes/inversions/spreads and ROOT policies; history and register jumps', flush=True)

        # Direct fixed-SIZE calls reuse generator output, while preserving each
        # complete progression's configuration and history for AUTO scoring.
        for quality in range(8):
            raw = []
            for m in machines:
                m.configure(2, 0)
                m.uc.mem_write(m.sym['ch_current'], bytes((quality,)))
            for pitch in progression:
                pools = [m.generate(pitch)[1] for m in machines]
                assert pools[0] == pools[1], (quality, pitch, pools)
                raw.append(pools[0])
            for size in range(1, 4):
                for spread in range(3):
                    for voic in range(5):
                        for root_mode in range(4):
                            config = size << 7 | root_mode << 5 | spread << 3 | voic
                            for m in machines:
                                m.uc.mem_write(m.scratch+8, bytes(8))
                            for pool in raw:
                                results = []
                                for m in machines:
                                    m.uc.mem_write(m.scratch, pool)
                                    m.c('mh_size_voice_c', m.scratch, m.scratch+8,
                                        config, quality, 0)
                                    results.append((bytes(m.uc.mem_read(m.scratch, 4)),
                                                    bytes(m.uc.mem_read(m.scratch+8, 8))))
                                same('fixed_size', results, (config, quality, pool))
        print('[ok] fixed SIZE 2/3/4: every recipe, inversion, spread and ROOT policy; stable AUTO histories', flush=True)

    for boundary in range(4):
        for low, high in ((0, 0), (0, 1), (-1, 0), (-1, 1), (-7, 7), (-21, 21)):
            for code in range(16):
                for m in machines:
                    m.configure(2, 0)
                    m.c('ha_bank_reset_c', 0)
                    m.c('ha_runtime_reset_c')
                    # Odd/even nibbles and inherit use the same configured
                    # base, then alternate independent per-step phases.
                    m.uc.mem_write(m.sym['ha_lanes']+32,
                                   bytes((low & 255, high, boundary, 3, 9)))
                    m.c('ha_set_c', 0, 0, 0, 0, code)
                    m.c('ha_set_c', 0, 0, 0, 1, code)
                for event in range(16):
                    results = []
                    for m in machines:
                        if event == 8:
                            m.c('ha_transport_c')
                        m.c('ha_fire_c', 0, 0, 0, event % 2)
                        row = [m.c('ha_shift_c', note, 0, 0) for note in (0, 48, 127)]
                        if event % 5:
                            m.c('ha_sounded_c', 0)
                            m.c('ha_sounded_c', 0)
                        row.append(m.c('ha_shift_c', 48, 0, 0))
                        results.append(row)
                    same('accumulator', results, (boundary, low, high, code, event))
    for note in (-1, 0, 127, 128):
        for track in (0, 7, 8, 0xffffffff):
            for context in (0, 63, 64, 0xffffffff):
                same('accumulator_invalid_arguments',
                     [m.c('ha_shift_c', note, track, context) for m in machines],
                     (note, track, context))
    for policy in range(4):
        results = []
        for m in machines:
            m.configure(2, 0)
            m.c('ha_bank_reset_c', 0)
            m.c('ha_runtime_reset_c')
            for pattern in (0, 1):
                m.uc.mem_write(m.sym['ha_lanes']+pattern*8*37+32,
                               bytes((0, 7, 0, policy, 9)))
            row = []
            # Fresh identity and START coincide on the first event. Then
            # START coincides with a real pattern change and nonzero phase.
            for pattern in (0, 1):
                m.c('ha_transport_c')
                m.c('ha_fire_c', 0, pattern, 0, 0)
                row.append(m.c('ha_shift_c', 48, 0, 0))
                m.c('ha_sounded_c', 0)
                m.c('ha_sounded_c', 0)
            m.c('ha_fire_c', 0, 1, 0, 0)
            row.append(m.c('ha_shift_c', 48, 0, 0))
            m.c('ha_transport_c')
            m.c('ha_fire_c', 0, 1, 0, 0)
            row.append(m.c('ha_shift_c', 48, 0, 0))
            results.append(row)
        result = same('accumulator_reset', results, policy)
        assert result == [48, 48 if policy else 50, 50 if policy else 52,
                          48 if policy & 1 else 50 if policy else 52], (policy, result)
    for step in range(64):
        for code in range(16):
            values = []
            for m in machines:
                m.c('ha_set_c', 0, 0, 0, step, code)
                values.append(m.c('ha_lock_c', 0, 0, 0, step))
            result = same('accumulator_locks', values, (step, code))
            assert result == code, (step, code, result)
    print('[ok] accumulator all nibble codes/boundaries; repeat, silent, restart and invalid arguments', flush=True)
    report = dict(cases=counts, total=sum(counts.values()),
                  section=args.section,
                  natural_auto_scored_voices=scoring,
                  baseline=str(args.baseline), candidate=str(args.candidate),
                  runtime_sha256=[hashlib.sha256((p/'platform/runtime/runtime.elf').read_bytes()).hexdigest()
                                  for p in (args.baseline, args.candidate)],
                  evidence=('Executed linked ColdFire before/after behavior; independent quantization, spread and reset-policy oracles'
                            if args.section == 'all' else
                            'Executed linked ColdFire accumulator before/after behavior; independent reset-policy oracle'),
                  hardware_tested=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
