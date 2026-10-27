#!/usr/bin/env python3
"""Profile and compare the actual linked ColdFire Sophie renderer.

Use --baseline-ref COMMIT for exact audio/state regression checks and paired
instruction counts. The receipt pins assembly and ELF hashes; retained objects
make comparison reproducible after a rebuild. Counts are not hardware cycles.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import re
import struct
import subprocess
import tempfile

from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.m68k_const import (
    UC_CPU_M68K_CFV4E, UC_M68K_REG_A7, UC_M68K_REG_PC, UC_M68K_REG_SR,
    UC_M68K_REG_D0, UC_M68K_REG_D2, UC_M68K_REG_D3, UC_M68K_REG_D4,
    UC_M68K_REG_D5, UC_M68K_REG_D6, UC_M68K_REG_D7, UC_M68K_REG_A2,
    UC_M68K_REG_A3, UC_M68K_REG_A4, UC_M68K_REG_A5, UC_M68K_REG_A6,
)

ROOT = Path(__file__).resolve().parents[2]
STATE, CONTROLS, OUT, STACK, RETURN = 0x21000, 0x23000, 0x24000, 0x28000, 0x20000
VOICE_PREFIX = 246  # m68k ABI: engine/params/block/history through primed/trigger
PRESERVED = (UC_M68K_REG_D2, UC_M68K_REG_D3, UC_M68K_REG_D4, UC_M68K_REG_D5,
             UC_M68K_REG_D6, UC_M68K_REG_D7, UC_M68K_REG_A2, UC_M68K_REG_A3,
             UC_M68K_REG_A4, UC_M68K_REG_A5, UC_M68K_REG_A6)


def output(command):
    return subprocess.check_output(command, cwd=ROOT, text=True)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sections(elf):
    result = {}
    lines = output(['m68k-elf-objdump', '-h', str(elf)]).splitlines()
    for index, line in enumerate(lines[:-1]):
        fields = line.split()
        if len(fields) >= 7 and fields[0].isdigit() and 'ALLOC' in lines[index + 1]:
            result[fields[1]] = dict(size=int(fields[2], 16), address=int(fields[3], 16))
    return result


def build(assembly, directory, name):
    source, obj, elf = (directory / (name + suffix) for suffix in ('.s', '.o', '.elf'))
    source.write_bytes(assembly)
    subprocess.run(['m68k-elf-as', '-mcpu=54455', '-o', str(obj), str(source)], check=True)
    subprocess.run(['m68k-elf-gcc', '-mcpu=54455', '-nostdlib', '-Wl,-Ttext=0x10000',
                    '-Wl,-e,sf_fill', str(obj), '-lgcc', '-o', str(elf)], check=True)
    return elf


class Runtime:
    """Separate machine per side; no replacement host DSP or timing oracle."""
    def __init__(self, elf):
        self.symbols, self.sizes = {}, {}
        for line in output(['m68k-elf-nm', '-S', str(elf)]).splitlines():
            fields = line.split()
            if len(fields) in (3, 4):
                self.symbols[fields[-1]] = int(fields[0], 16)
                if len(fields) == 4:
                    self.sizes[fields[-1]] = int(fields[1], 16)
        self.stride = self.sizes['sf_voices'] // 8
        assert self.stride >= VOICE_PREFIX, self.stride
        self.opcodes, self.owners = {}, {}
        owner = ''
        for line in output(['m68k-elf-objdump', '-d', str(elf)]).splitlines():
            if match := re.match(r'^[0-9a-f]+ <([^>]+)>:', line):
                owner = match[1]
            if match := re.match(r'^\s*([0-9a-f]+):\s+(?:[0-9a-f]{4}\s+)+\s*([a-z][a-z0-9.]+)', line):
                address = int(match[1], 16)
                self.opcodes[address], self.owners[address] = match[2], owner
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / 'runtime.bin'
            subprocess.run(['m68k-elf-objcopy', '-O', 'binary', str(elf), str(binary)], check=True)
            image = binary.read_bytes()
        layout = sections(elf)
        base = min(item['address'] for item in layout.values())
        end = max(item['address'] + item['size'] for item in layout.values())
        assert end - base < 0x4000000, 'unexpected runtime memory footprint'
        self.uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        self.uc.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
        self.uc.mem_map(base & ~4095, ((end + 4095) & ~4095) - (base & ~4095))
        self.uc.mem_write(base, image)
        self.uc.mem_map(0x20000, 0x10000)
        self.uc.mem_map(0x100b1000, 0x25000)
        self.uc.mem_map(0x80004000, 0x2000)
        self.uc.reg_write(UC_M68K_REG_SR, 0x2000)
        self.counts, self.functions = Counter(), Counter()
        self.min_stack = STACK
        self.uc.hook_add(UC_HOOK_CODE, self.tick)
        for track in range(8):
            state = bytearray(128)
            struct.pack_into('>I', state, 12, 25480119)
            struct.pack_into('>I', state, 24, 32768)
            struct.pack_into('>H', state, 38, 32768)
            self.uc.mem_write(STATE + 128 * track, bytes(state))
            self.controls(track, 50, 0, 0, 0)
            self.marker(track, True)

    def tick(self, uc, address, _size, _user):
        self.counts[self.opcodes.get(address, 'unknown')] += 1
        self.functions[self.owners.get(address, 'unknown')] += 1
        self.min_stack = min(self.min_stack, uc.reg_read(UC_M68K_REG_A7))

    def call(self, name, *arguments):
        self.counts.clear()
        self.functions.clear()
        self.min_stack = STACK
        self.uc.reg_write(UC_M68K_REG_A7, STACK)
        for index, register in enumerate(PRESERVED):
            self.uc.reg_write(register, 0x15300000 + index * 0x10101)
        self.uc.mem_write(STACK, struct.pack('>' + 'I' * (1 + len(arguments)), RETURN, *arguments))
        self.uc.emu_start(self.symbols[name], RETURN, count=1000000)
        assert self.uc.reg_read(UC_M68K_REG_PC) == RETURN, (name, 'instruction limit')
        assert self.uc.reg_read(UC_M68K_REG_A7) == STACK + 4, (name, 'stack imbalance')
        for index, register in enumerate(PRESERVED):
            assert self.uc.reg_read(register) == 0x15300000 + index * 0x10101, (name, 'callee-saved register', register)
        assert 'unknown' not in self.counts, self.counts
        return dict(instructions=sum(self.counts.values()),
                    multiplies=sum(n for k, n in self.counts.items() if k.startswith('mul')),
                    divides=sum(n for k, n in self.counts.items() if k.startswith(('div', 'rem'))),
                    max_stack_bytes=STACK - self.min_stack, functions=dict(self.functions))

    def marker(self, track, selected):
        address = 0x100b14f0 + 0x448 * track
        self.uc.mem_write(address, (b'FMSYNTH-SOPHIE.wav' if selected else b'FMSYNTH.wav') + b'\0')
        self.uc.mem_write(0x800049d8 + 0xa8 * track + 8, struct.pack('>I', address))

    def controls(self, track, color, metal, feedback, sweep):
        self.uc.mem_write(CONTROLS + 16 * track, struct.pack('>6H', 0x4000, color << 8,
                          metal << 8, 0x4000, feedback << 8, (sweep + 64) << 8))

    def state(self, track, offset, fmt, value):
        self.uc.mem_write(STATE + 128 * track + offset, struct.pack('>' + fmt, value))

    def fill(self, track, n):
        # Check both ends even for n=0 and declined/unsupported calls.
        self.uc.mem_write(OUT - 16, b'\xa5' * (16 + 64 * 8 + 16))
        result = self.call('sf_fill', track, STATE + 128 * min(track, 7),
                           CONTROLS + 16 * min(track, 7), OUT, n)
        assert bytes(self.uc.mem_read(OUT - 16, 16)) == b'\xa5' * 16
        assert bytes(self.uc.mem_read(OUT + n * 8, 16)) == b'\xa5' * 16
        return result

    def snapshot(self):
        # Private optimization caches may be appended, but existing offsets
        # must remain fixed for this byte comparison of baseline semantics.
        return {
            'voices': b''.join(bytes(self.uc.mem_read(self.symbols['sf_voices'] + self.stride * track,
                                                     VOICE_PREFIX)) for track in range(8)),
            'native_state': bytes(self.uc.mem_read(STATE, 128 * 8)),
            'output_and_guards': bytes(self.uc.mem_read(OUT - 16, 16 + 64 * 8 + 16)),
            **{name: bytes(self.uc.mem_read(self.symbols[name], size)) for name, size in
               (('sf_active', 8), ('sf_samples', 32), ('sf_unsupported', 32))},
        }


def compare_snapshots(baseline, candidate, label):
    for field, expected in baseline.items():
        actual = candidate[field]
        assert len(actual) == len(expected), (label, field, 'observation size differs')
        if actual != expected:
            offset = next(i for i, (a, b) in enumerate(zip(expected, actual)) if a != b)
            raise AssertionError(f'{label}: {field} differs at byte {offset}: '
                                 f'baseline={expected[offset]:02x}, candidate={actual[offset]:02x}')


def operations():
    """Deterministic stateful boundary matrix, with controls between calls."""
    yield ('fill', 0, 16)  # inactive path before begin
    yield ('fill', 8, 16)  # invalid track cannot disturb another voice
    yield ('call', 'sf_begin', 8)
    for track in range(8):
        yield ('call', 'sf_begin', track)
    # Every count on every track, with high/low controls and fractional pitch.
    for n in range(33):
        for track in range(8):
            yield ('controls', track, (n * 7 + track * 11) & 127,
                   (n * 13 + track * 17) & 127, (n * 19 + track * 23) & 127,
                   ((n * 29 + track * 31) & 127) - 64)
            yield ('fill', track, n)
    # FINE changes use their resulting native increments. The unchanged FINE
    # UI/parameter preparation is outside this standalone link.
    pitches = [0, 1, 694202, 694203, 694204,
               25333444, 25480118, 25480119, 25480120, 25627715,
               0x7fffffff, 0xffffffff]
    for phase in (8, 9, 24576, 24577):
        # First native increment that reaches this unclamped engine phase.
        boundary = ((phase * 40960 + 146) // 147) * 256
        pitches.extend((boundary - 1, boundary, boundary + 1))
    for index, pitch in enumerate(pitches):
        track = index % 8
        yield ('state', track, 12, 'I', pitch)
        for n in (0, 1, 15, 16, 17, 31, 32):
            yield ('fill', track, n)
    # Native ramp updates happen per call; compare identical split sequences
    # instead of assuming one n=32 call equals two n=16 calls.
    for previous, target in ((0, 0), (0, 32768), (32768, 0), (1, 32767),
                             (32767, 1), (16384, 16384), (32769, 32768), (65535, 0)):
        for n in (0, 1, 2, 7, 15, 16, 17, 23, 31, 32):
            yield ('state', 0, 38, 'H', previous)
            yield ('state', 0, 24, 'I', target)
            yield ('fill', 0, n)
    for track in range(8):
        for n in (0, 1, 16, 32):
            yield ('state', track, 80, 'B', 1)
            yield ('fill', track, n)
            yield ('state', track, 80, 'B', 0)
        for n in (33, 64):
            yield ('fill', track, n)
        yield ('call', 'sf_begin', track)
        yield ('fill', track, 1)
        yield ('marker', track, False)
        yield ('call', 'sf_begin', track)
        yield ('fill', track, 16)
        yield ('marker', track, True)
        yield ('call', 'sf_begin', track)
        yield ('fill', track, 32)
    rng = random.Random(0x534f5048)
    for index in range(192):
        track = rng.randrange(8)
        if index % 5 == 0:
            yield ('call', 'sf_begin', track)
        if index % 3 == 0:
            yield ('controls', track, rng.randrange(128), rng.randrange(128),
                   rng.randrange(128), rng.randrange(-64, 64))
        yield ('fill', track, rng.choice((0, 1, 2, 3, 7, 11, 13, 15, 16, 17, 23, 29, 31, 32)))


def equivalence(baseline_elf, candidate_elf):
    baseline, candidate = Runtime(baseline_elf), Runtime(candidate_elf)
    digest, calls, maximum_stack = hashlib.sha256(), Counter(), {'baseline': 0, 'candidate': 0}
    for index, operation in enumerate(operations()):
        method, *arguments = operation
        label = f'operation {index}: {operation}'
        old = getattr(baseline, method)(*arguments)
        new = getattr(candidate, method)(*arguments)
        if method in ('fill', 'call'):
            calls[method] += 1
            if method == 'fill':
                assert baseline.uc.reg_read(UC_M68K_REG_D0) == candidate.uc.reg_read(UC_M68K_REG_D0), label
            for side, result in (('baseline', old), ('candidate', new)):
                maximum_stack[side] = max(maximum_stack[side], result['max_stack_bytes'])
            before, after = baseline.snapshot(), candidate.snapshot()
            compare_snapshots(before, after, label)
            for field in sorted(before):
                digest.update(before[field])
    # Corrupt snapshots to ensure none of these observations silently vanish.
    reference = baseline.snapshot()
    negative_controls = []
    for field, offset in (('output_and_guards', 16), ('voices', 0), ('voices', 232),
                          ('native_state', 38), ('sf_samples', 0), ('sf_active', 0),
                          ('sf_unsupported', 0)):
        mutated = dict(reference)
        value = bytearray(mutated[field])
        value[offset] ^= 1
        mutated[field] = bytes(value)
        try:
            compare_snapshots(reference, mutated, 'negative control')
        except AssertionError:
            negative_controls.append(f'{field}[{offset}]')
        else:
            raise AssertionError(f'undetected negative control: {field}[{offset}]')
    return dict(exact=True, calls=dict(calls), operations=index + 1,
                observation_sha256=digest.hexdigest(), max_stack_bytes=maximum_stack,
                compared_voice_prefix_bytes=VOICE_PREFIX, tracks=8, frame_counts=list(range(33)),
                negative_controls=negative_controls,
                coverage=['all engine/parameter/block/history/fraction/trigger bytes', 'native AMP/state',
                          'all track counters', 'PTCH/FINE resulting pitch increments', 'changing FUSE controls',
                          'irregular split calls', 'active retriggers', 'marker transitions', 'inactive/invalid tracks',
                          'unsupported polyphony and n > 32', 'gain attack/release/steady/saturation',
                          'callee-saved registers', 'stack balance', 'output guards'])


SCENARIOS = {
    'plain': dict(pitch=25480119, color=50, metal=0, feedback=0, sweep=0, tracks=1),
    'metallic': dict(pitch=25480119, color=50, metal=80, feedback=48, sweep=0, tracks=1),
    'sweep': dict(pitch=25480119, color=50, metal=80, feedback=48, sweep=63, tracks=1),
    'two_tracks': dict(pitch=25480119, color=50, metal=80, feedback=48, sweep=0, tracks=2),
    'eight_tracks': dict(pitch=25480119, color=50, metal=80, feedback=48, sweep=0, tracks=8),
}
for label, previous, target in (('partial_gain', 8192, 8192), ('attack', 2048, 16384),
                                 ('release', 32768, 8192), ('zero_gain', 0, 0)):
    SCENARIOS[label] = dict(SCENARIOS['metallic'], gain_from=previous, gain_to=target)


def profile(elf, scenario):
    runtime = Runtime(elf)
    for track in range(scenario['tracks']):
        runtime.state(track, 12, 'I', scenario['pitch'])
        runtime.controls(track, scenario['color'], scenario['metal'], scenario['feedback'], scenario['sweep'])
        runtime.call('sf_begin', track)
    calls = []
    for _ in range(24):
        for track in range(scenario['tracks']):
            if 'gain_from' in scenario:
                runtime.state(track, 38, 'H', scenario['gain_from'])
                runtime.state(track, 24, 'I', scenario['gain_to'])
            calls.append(runtime.fill(track, 16))
    warm = calls[8 * scenario['tracks']:]
    result = {
        'cold': calls[:scenario['tracks']],
        # Aggregate tracks per 16-frame interval, as in the original profiler.
        # The warm window contains exactly 16 intervals.
        'warm_per_16_frames': {field: sum(item[field] for item in warm) / 16
                               for field in ('instructions', 'multiplies', 'divides')},
        'warm_by_function': {name: sum(item['functions'].get(name, 0) for item in warm) / 16
                             for name in sorted({name for item in warm for name in item['functions']})},
        'max_stack_bytes': max(item['max_stack_bytes'] for item in calls),
        'calls': len(warm),
    }
    transitions = {}
    for label, offset, fmt, value in (('pitch_change', 12, 'I', scenario['pitch'] + 1000),
                                      ('attack', 38, 'H', 0), ('release', 24, 'I', 0)):
        runtime.state(0, offset, fmt, value)
        transitions[label] = runtime.fill(0, 16)
    runtime.controls(0, 127, 127, 127, -64)
    transitions['control_change'] = runtime.fill(0, 16)
    runtime.call('sf_begin', 0)
    transitions['retrigger'] = runtime.fill(0, 16)
    result['transitions'] = transitions
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', type=Path, help='Use a linked standalone adapter or full firmware runtime ELF')
    parser.add_argument('--assembly', type=Path, default=ROOT / 'modules/sophie/adapter.s')
    parser.add_argument('--baseline-ref', help='Git commit containing the baseline adapter.s')
    parser.add_argument('--baseline-assembly', type=Path, help='Saved baseline instead of --baseline-ref')
    parser.add_argument('--output', type=Path, default=ROOT / 'out/sophie-cpu.json')
    args = parser.parse_args()
    if args.baseline_ref and args.baseline_assembly:
        parser.error('choose --baseline-ref or --baseline-assembly')
    args.output = args.output.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    artifacts = args.output.with_suffix('')
    artifacts.mkdir(parents=True, exist_ok=True)
    assembly = None if args.elf else args.assembly.read_bytes()
    if args.elf:
        elf = artifacts / 'candidate.elf'
        elf.write_bytes(args.elf.read_bytes())
    else:
        elf = build(assembly, artifacts, 'candidate')
    receipt = dict(adapter_sha256=None if assembly is None else sha(assembly),
                   profiled_elf_sha256=sha(elf.read_bytes()), hardware_cycles=False,
                   verifier_sha256=sha(Path(__file__).read_bytes()),
                   linked_sections=sections(elf),
                   samples_per_call=16, cpu_model='Unicorn M68K CFV4E',
                   compiler=output(['m68k-elf-gcc', '--version']).splitlines()[0],
                   source_elf=str(args.elf.resolve()) if args.elf else None,
                   scope='direct function calls into the retained linked ColdFire ELF; excludes firmware scheduling, caches and physical hardware')
    baseline_elf = None
    if args.baseline_ref or args.baseline_assembly:
        baseline_ref = output(['git', 'rev-parse', args.baseline_ref + '^{commit}']).strip() if args.baseline_ref else None
        baseline = (output(['git', 'show', baseline_ref + ':modules/sophie/adapter.s']).encode()
                    if baseline_ref else args.baseline_assembly.read_bytes())
        baseline_elf = build(baseline, artifacts, 'baseline')
        receipt['baseline'] = dict(commit=baseline_ref, adapter_sha256=sha(baseline),
                                   linked_sections=sections(baseline_elf),
                                   profiled_elf_sha256=sha(baseline_elf.read_bytes()))
        receipt['equivalence'] = equivalence(baseline_elf, elf)
        print('[ok] exact ColdFire audio/state comparison', receipt['equivalence']['calls'], flush=True)
    receipt['scenarios'] = {name: profile(elf, case) for name, case in SCENARIOS.items()}
    if baseline_elf:
        receipt['baseline']['scenarios'] = {name: profile(baseline_elf, case) for name, case in SCENARIOS.items()}
        receipt['instruction_reduction_percent'] = {
            name: 100 * (1 - case['warm_per_16_frames']['instructions'] /
                         receipt['baseline']['scenarios'][name]['warm_per_16_frames']['instructions'])
            for name, case in receipt['scenarios'].items()}
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    for name, case in receipt['scenarios'].items():
        print(name, case['warm_per_16_frames'], 'stack', case['max_stack_bytes'])
    print('receipt', args.output)


if __name__ == '__main__':
    main()
