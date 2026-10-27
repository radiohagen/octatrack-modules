#!/usr/bin/env python3
"""Compare two real ColdFire codecs, including invalid scale/ABI behavior.

Pass the frozen baseline codec.s via --baseline-source. This complements the
musical oracle gate with exact fallback comparisons and instruction counts;
counts describe emulator work, not hardware cycles or measured audio load.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.m68k_const import *

ROOT = Path(__file__).resolve().parents[2]
REGISTERS = (UC_M68K_REG_D1, UC_M68K_REG_D2, UC_M68K_REG_D3,
             UC_M68K_REG_D4, UC_M68K_REG_D5, UC_M68K_REG_D6,
             UC_M68K_REG_D7, UC_M68K_REG_A0, UC_M68K_REG_A1,
             UC_M68K_REG_A2, UC_M68K_REG_A3, UC_M68K_REG_A4,
             UC_M68K_REG_A5, UC_M68K_REG_A6)


class Codec:
    def __init__(self, source, out):
        subprocess.run(['m68k-elf-as', '-mcpu=54455', '-o', str(out/'codec.o'),
                        str(source)], check=True)
        subprocess.run(['m68k-elf-ld', '-Ttext=0x47000000', '-e', 'hd_encode',
                        '-o', str(out/'codec.elf'), str(out/'codec.o')], check=True)
        subprocess.run(['m68k-elf-objcopy', '-O', 'binary', str(out/'codec.elf'),
                        str(out/'codec.bin')], check=True)
        nm = subprocess.check_output(['m68k-elf-nm', str(out/'codec.elf')], text=True)
        self.symbols = {n: int(a, 16) for a, n in re.findall(
            r'^([0-9a-f]+) [Tt] (hd_\w+)$', nm, re.M)}
        self.uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        self.uc.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
        self.uc.mem_map(0x47000000, 0x10000)
        data = (out/'codec.bin').read_bytes()
        assert len(data) < 0x8000
        self.uc.mem_write(0x47000000, data)
        self.bytes = len(data)
        self.uc.hook_add(UC_HOOK_CODE, self.before)

    def before(self, uc, pc, size, data):
        if pc == 0x4700fff0:
            self.returned = True
            uc.emu_stop()
        else:
            self.instructions += 1

    def call(self, name, value, scale):
        uc = self.uc
        self.returned = False
        self.instructions = 0
        uc.reg_write(UC_M68K_REG_SR, 0x2000)
        uc.reg_write(UC_M68K_REG_A7, 0x47008000)
        uc.mem_write(0x47008000, bytes.fromhex('4700fff0'))
        for reg in REGISTERS:
            uc.reg_write(reg, 0x12345678)
        uc.reg_write(UC_M68K_REG_D0, value & 0xffffffff)
        uc.reg_write(UC_M68K_REG_D1, scale & 0xffffffff)
        uc.emu_start(self.symbols[name], 0, count=2000)
        assert self.returned, (name, value, scale)
        assert uc.reg_read(UC_M68K_REG_A7) == 0x47008004
        assert uc.reg_read(UC_M68K_REG_SR) & 0xff00 == 0x2000
        for reg in REGISTERS:
            expected = scale & 0xffffffff if reg == UC_M68K_REG_D1 else 0x12345678
            assert uc.reg_read(reg) == expected, (name, reg, value, scale)
        return uc.reg_read(UC_M68K_REG_D0), self.instructions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-source', type=Path, required=True)
    parser.add_argument('--candidate-source', type=Path,
                        default=ROOT/'modules/midi-harmony/codec.s')
    parser.add_argument('--require-reduction', action='store_true',
                        help='Also require fewer aggregate instructions for both codecs.')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='harmony-codec-equivalence-') as tmp:
        out = Path(tmp)
        (out/'before').mkdir()
        (out/'after').mkdir()
        before = Codec(args.baseline_source, out/'before')
        after = Codec(args.candidate_source, out/'after')
        counts = {name: {'cases': 0, 'before': 0, 'after': 0,
                         'before_max': 0, 'after_max': 0}
                  for name in ('hd_encode', 'hd_decode')}
        scales = [m*64+k*4 for m in range(7) for k in range(12)]
        # Low unused bits retain their native meaning. Malformed tonic/mode,
        # negative and wide values retain the old C-major fallback.
        aliases = [s+low for s in scales for low in (1, 2, 3)]
        invalid = [m*64+k*4 for m in range(7) for k in range(12, 16)]
        invalid += [448, 449, 511, 512, 65535, 0x7fffffff, -1, -2, -0x80000000]
        compared = 0
        for scale in scales+aliases+invalid:
            for name, values in (('hd_encode', range(128)), ('hd_decode', range(84))):
                for value in values:
                    old, old_n = before.call(name, value, scale)
                    new, new_n = after.call(name, value, scale)
                    assert new == old, (name, value, scale, old, new)
                    compared += 1
                    if scale in scales:
                        row = counts[name]
                        row['cases'] += 1
                        row['before'] += old_n
                        row['after'] += new_n
                        row['before_max'] = max(row['before_max'], old_n)
                        row['after_max'] = max(row['after_max'], new_n)
            for name, values in (('hd_encode', (128, 255, -1, 0x7fffffff)),
                                 ('hd_decode', (84, 127, 255, -1, 0x7fffffff))):
                for value in values:
                    assert after.call(name, value, scale)[0] == before.call(name, value, scale)[0]
                    compared += 1
        for row in counts.values():
            if args.require_reduction:
                assert row['after'] < row['before'], row
            row['reduction_percent'] = round(100*(1-row['after']/row['before']), 2)
        print(json.dumps({'cases': compared, 'instructions': counts,
                          'codec_bytes': {'before': before.bytes, 'after': after.bytes},
                          'register_stack_sr_preservation': 'passed',
                          'require_reduction': args.require_reduction,
                          'evidence': 'ColdFire instructions', 'hardware_tested': False}))


if __name__ == '__main__':
    main()
