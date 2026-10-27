#!/usr/bin/env python3
"""Prove the CPU SEM's exact EMAC arithmetic and complete caller-state preservation.

Builds isolated probes from the current source, checks the corrected Unicorn
self-test before executing them, and compares full/half-rate filters against
the independent scalar int64 reference. No firmware image or device is used.
"""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import random
import runpy
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]

# Save/restore probes deliberately use raw integer-mode views. Comparing only
# fractional MOVCLR output would miss lost low bits and accumulator extensions.
STATE_ASM = r"""
.text
.global ss_probe_load,ss_probe_dump
ss_probe_load:
 move.l 4(%sp),%a0
 move.l #0,%macsr
 move.l 4(%a0),%d0
 move.l %d0,%acc0
 move.l 8(%a0),%d0
 move.l %d0,%acc1
 move.l 12(%a0),%d0
 move.l %d0,%acc2
 move.l 16(%a0),%d0
 move.l %d0,%acc3
 move.l 20(%a0),%d0
 move.l %d0,%accext01
 move.l 24(%a0),%d0
 move.l %d0,%accext23
 move.l 28(%a0),%d0
 move.l %d0,%mask
 move.l (%a0),%d0
 move.l %d0,%macsr
 rts
ss_probe_dump:
 move.l 4(%sp),%a0
 move.l %macsr,%d1
 move.l %d1,(%a0)
 move.l #0,%macsr
 move.l %acc0,%d0
 move.l %d0,4(%a0)
 move.l %acc1,%d0
 move.l %d0,8(%a0)
 move.l %acc2,%d0
 move.l %d0,12(%a0)
 move.l %acc3,%d0
 move.l %d0,16(%a0)
 move.l %accext01,%d0
 move.l %d0,20(%a0)
 move.l %accext23,%d0
 move.l %d0,24(%a0)
 move.l %mask,%d0
 move.l %d0,28(%a0)
 move.l %d1,%macsr
 rts
"""

CF_SOURCE = r"""
#include <stdint.h>
#define SS_HOST_TEST
#include "tables.h"
#include "filter.h"
void ss_probe_reset(struct ss_filter *s) { ss_filter_reset(s); }
void ss_probe_filter(struct ss_filter *s,const struct ss_filter_params *p,
                     uint32_t stamp,int16_t *audio,unsigned n,unsigned rate) {
    if(rate==1)ss_filter_run(s,p,stamp,audio,n);
    else ss_filter_half(s,p,stamp,audio,n);
}
int32_t ss_probe_multiply(int32_t a,int32_t b) {
    struct ss_emac_state saved=ss_filter_enter();
    int32_t result=ss_filter_mul(a,ss_filter_coefficient(b));
    ss_filter_leave(saved);
    return result;
}
"""

HOST_SOURCE = r"""
#include <stdint.h>
#include "tables.h"
#include "filter.h"
#include "filter_reference.h"
void ss_probe_reference(struct ss_filter *s,const struct ss_filter_params *p,
                        uint32_t stamp,int16_t *audio,unsigned n,unsigned rate) {
    ss_filter_reference_rate(s,p,stamp,audio,n,rate);
}
void ss_probe_bounds(int32_t *out) {
    for(unsigned i=0;i<4;++i)out[i]=0;
    for(unsigned cutoff=0;cutoff<128;++cutoff)
        for(unsigned res=0;res<128;++res)
            for(unsigned rate=1;rate<=2;++rate) {
                int32_t g=rate==2?ss_filter_half_g[cutoff]:ss_filter_g[cutoff];
                int32_t k=ss_filter_damping[res];
                int32_t a1=rate==2?ss_filter_half_a1[res][cutoff]:ss_filter_a1[res][cutoff];
                if(g>out[0])out[0]=g;
                if(k>out[1])out[1]=k;
                if(g+k>out[2])out[2]=g+k;
                if(a1>out[3])out[3]=a1;
            }
}
"""


class State(ctypes.Structure):
    _fields_ = [(n, ctypes.c_int32) for n in ('s0', 's1', 'a1', 'a2', 'a3', 'damping')]
    _fields_ += [('envelope', ctypes.c_uint32), ('stamp', ctypes.c_uint32),
                ('wet', ctypes.c_uint16), ('type', ctypes.c_uint8), ('ready', ctypes.c_uint8)]


class Params(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint8) for n in ('cutoff', 'resonance', 'amount', 'decay', 'type')]


def state_pack(s):
    return struct.pack('>6i2IH2B', *[getattr(s, n) for n, _ in State._fields_])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--emulator-root', type=Path, default=ROOT,
                    help='Octabam tree supplying tools/toolpath.py and the emulator self-test')
    ap.add_argument('--output', type=Path, default=ROOT/'out/supersaw-emac.json')
    args = ap.parse_args()
    sys.path.insert(0, str(args.emulator_root/'tools'))
    import toolpath  # noqa: F401
    from emu_bringup import emac_selftest
    from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.m68k_const import (UC_CPU_M68K_CFV4E, UC_M68K_REG_SR,
                                  UC_M68K_REG_A7, UC_M68K_REG_PC, UC_M68K_REG_D0)
    ok, detail = emac_selftest()
    if not ok:
        raise SystemExit('Corrected ColdFire EMAC is required: '+detail)

    module = ROOT/'modules/supersaw'
    flags = runpy.run_path(str(module/'generate.py'))['FLAGS']
    with tempfile.TemporaryDirectory(prefix='supersaw-emac-') as temp:
        work = Path(temp)
        (work/'probe.c').write_text(CF_SOURCE)
        (work/'reference.c').write_text(HOST_SOURCE)
        (work/'state.s').write_text(STATE_ASM)
        subprocess.run(['m68k-elf-gcc', *flags, '-I', str(module), '-c', str(work/'probe.c'),
                        '-o', str(work/'probe.o')], check=True)
        subprocess.run(['m68k-elf-as', '-mcpu=54455', str(work/'state.s'),
                        '-o', str(work/'state.o')], check=True)
        subprocess.run(['m68k-elf-ld', '-Ttext=0x100000', '--entry=ss_probe_filter',
                        str(work/'probe.o'), str(work/'state.o'), '-o', str(work/'probe.elf')], check=True)
        subprocess.run(['m68k-elf-objcopy', '-O', 'binary', str(work/'probe.elf'),
                        str(work/'probe.bin')], check=True)
        subprocess.run(['cc', '-O2', '-shared', '-fPIC', '-I', str(module),
                        str(work/'reference.c'), '-o', str(work/'reference.dylib')], check=True)
        host = ctypes.CDLL(str(work/'reference.dylib'))
        host.ss_probe_reference.argtypes = [ctypes.POINTER(State), ctypes.POINTER(Params),
            ctypes.c_uint32, ctypes.POINTER(ctypes.c_int16), ctypes.c_uint32, ctypes.c_uint32]
        bounds = (ctypes.c_int32*4)()
        host.ss_probe_bounds(bounds)
        g, damping, coefficient, normalizer = bounds
        # A ramp takes truncated steps between two bounded coefficients, so
        # its intermediate values remain inside the same endpoint bounds.
        wide_bound = 8388608+(8388607*coefficient+16383)//16384+8388607
        assert max(coefficient, normalizer)*8192 <= 0x7fffffff
        assert wide_bound*16 <= 0x7fffffff

        nm = subprocess.check_output(['m68k-elf-nm', str(work/'probe.elf')], text=True)
        symbols = {f[-1]: int(f[0], 16) for line in nm.splitlines() if len(f := line.split()) == 3}
        uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        uc.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
        data = (work/'probe.bin').read_bytes()
        uc.mem_map(0x100000, (len(data)+4095)&~4095)
        uc.mem_write(0x100000, data)
        uc.mem_map(0x10000, 0x30000)
        uc.reg_write(UC_M68K_REG_SR, 0x2000)
        ticks = [0]
        uc.hook_add(UC_HOOK_CODE, lambda *_: ticks.__setitem__(0, ticks[0]+1))

        def call(symbol, *values):
            uc.mem_write(0x30000, struct.pack('>'+'I'*(len(values)+1),
                         0x10000, *[v&0xffffffff for v in values]))
            uc.reg_write(UC_M68K_REG_A7, 0x30000)
            ticks[0] = 0
            uc.emu_start(symbols[symbol], 0x10000, count=100000)
            assert uc.reg_read(UC_M68K_REG_PC) == 0x10000, symbol
            assert uc.reg_read(UC_M68K_REG_A7) == 0x30004, 'stack imbalance'
            return uc.reg_read(UC_M68K_REG_D0), ticks[0]

        rng = random.Random(103)
        modes = [0, 0x20, 0x30, 0x40, 0x60, 0x80, 0xa0, 0xb0, 0xe0]

        def seed_emac(i):
            status = modes[i%len(modes)] | rng.randrange(16) | (rng.randrange(16)<<8)
            words = [status]+[rng.getrandbits(32) for _ in range(7)]
            uc.mem_write(0x22000, struct.pack('>8I', *words))
            call('ss_probe_load', 0x22000)
            call('ss_probe_dump', 0x22100)
            return bytes(uc.mem_read(0x22100, 32))

        def check_emac(before):
            call('ss_probe_dump', 0x22200)
            assert before == bytes(uc.mem_read(0x22200, 32)), 'EMAC caller state changed'

        edges = [-wide_bound, -8388607, -16385, -1, 0, 1, 16383, 8388607, wide_bound]
        for i in range(10000):
            before = seed_emac(i)
            a = edges[i%len(edges)] if i<100 else rng.randint(-wide_bound, wide_bound)
            b = [0, 1, 16383, 16384, coefficient][i%5] if i<100 else rng.randint(0, coefficient)
            got, _ = call('ss_probe_multiply', a, b)
            assert got == ((a*b)>>14)&0xffffffff, (i, a, b, got, (a*b)>>14)
            check_emac(before)

        samples = 0
        noops = 0
        for rate in (1, 2):
            oracle = State()
            call('ss_probe_reset', 0x23000)
            for block in range(4000):
                sizes = [0, 1, 2, 3, 7, 8, 15, 16] if rate==2 else [0, 1, 2, 3, 8, 16, 31, 32]
                n = sizes[block%8] if block%11==0 else (8 if rate==2 else 16)
                if block%50==0:
                    oracle = State()
                    call('ss_probe_reset', 0x23000)
                if block%7==0 or block==0:
                    p = Params(*[rng.randrange(256) for _ in range(4)], rng.choice([0, 1, 2, 3, 4, 255]))
                values = [rng.randint(-32768, 32767) for _ in range(n)]
                audio = (ctypes.c_int16*n)(*values)
                idle = not n or (p.type not in (1, 2, 3) and not oracle.wet)
                host.ss_probe_reference(ctypes.byref(oracle), ctypes.byref(p), block//17, audio, n, rate)
                before = seed_emac(block)
                uc.mem_write(0x24000, bytes(p))
                uc.mem_write(0x25000, struct.pack('>'+'h'*n, *values)+b'GUARD')
                _, cost = call('ss_probe_filter', 0x23000, 0x24000, block//17, 0x25000, n, rate)
                expected = struct.pack('>'+'h'*n, *audio)+b'GUARD'
                assert bytes(uc.mem_read(0x25000, 2*n+5)) == expected, ('samples', rate, block)
                assert bytes(uc.mem_read(0x23000, 36)) == state_pack(oracle), ('state', rate, block)
                check_emac(before)
                if idle:
                    assert cost<55, ('inactive path should skip EMAC setup', rate, block, cost)
                    noops += 1
                samples += n

        result = dict(result='pass', hardware_cycles=False, emac_selftest=detail,
            wide_multiply_cases=10000, filter_blocks=8000, filter_samples=samples,
            inactive_blocks=noops, source_rates=[44100, 22050],
            preserved=['MACSR', 'ACC0', 'ACC1', 'ACC2', 'ACC3', 'ACCEXT01', 'ACCEXT23', 'MASK'],
            incoming_modes=modes, arbitrary_condition_and_overflow_flags=True,
            bounds=dict(g=g, damping=damping, coefficient=coefficient, normalizer=normalizer,
                        wide_input=wide_bound, scaled_input=wide_bound*16,
                        scaled_coefficient=coefficient*8192),
            filter_sha256=hashlib.sha256((module/'filter.h').read_bytes()).hexdigest(),
            tables_sha256=hashlib.sha256((module/'tables.h').read_bytes()).hexdigest(),
            probe_sha256=hashlib.sha256(data).hexdigest())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
