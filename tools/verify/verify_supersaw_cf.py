#!/usr/bin/env python3
"""Run the linked ColdFire engine against host arithmetic; count instructions.

Uses Octabam's existing Unicorn CF harness pattern. This is arithmetic and ABI
proof, not a hardware cycle measurement; the port gate covers the full firmware.
"""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.m68k_const import (UC_CPU_M68K_CFV4E, UC_M68K_REG_A7,
                               UC_M68K_REG_PC, UC_M68K_REG_SR)
ROOT = Path(__file__).resolve().parents[2]
CASES = ((21426141,0,0,0,0), (21426141,127,127,0,0),
         (21426141,96,110,40,30), (1024,127,127,127,127),
         (0xffffffff,127,127,127,127), (42726141,65,100,127,90))
COUNTS = (0, 1, 3, 16, 32, 65)
PHASES = (0xfffffff0,0x12345678,0x87654321,0x7fffffff,0x80000000,0xabcdef01,0x3210fedc,0x11223344)


def main():
    runtime = ROOT/'out/platform/runtime'
    out = ROOT/'out/supersaw-cf'
    out.mkdir(parents=True,exist_ok=True)
    raw = subprocess.check_output(['m68k-elf-nm','-S',str(runtime/'runtime.elf')],text=True)
    sym = {f[-1]:int(f[0],16) for line in raw.splitlines() if len(f:=line.split()) in (3,4)}
    size = next(int(f[1],16) for line in raw.splitlines() if len(f:=line.split())==4 and f[3]=='ss_voices')
    assert size % 8 == 0
    stride = size//8
    headers = subprocess.check_output(['m68k-elf-objdump','-h',str(runtime/'runtime.elf')],text=True)
    base = int(next(line.split()[3] for line in headers.splitlines() if len(line.split())>3 and line.split()[1]=='.text'),16)
    data = (runtime/'runtime.bin').read_bytes()
    uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
    uc.mem_map(base & ~4095, (base%4096+len(data)+4095)&~4095)
    uc.mem_write(base,data)
    uc.mem_map(0x10000,0x20000)
    uc.reg_write(UC_M68K_REG_SR,0x2000)
    for name,n in [('ss_active',8),('ss_samples',32),('ss_unsupported',32),('ss_voices',size),('ss_descriptor',402)]:
        assert base <= sym[name] and sym[name]+n <= base+len(data), (name,'not initialized by loader')
        assert bytes(uc.mem_read(sym[name],n)) == bytes(n), (name,'not zero at boot')
    instructions = [0]
    def count(*_): instructions[0] += 1
    uc.hook_add(UC_HOOK_CODE,count)
    def call(name,*args):
        instructions[0] = 0
        uc.reg_write(UC_M68K_REG_A7,0x20000)
        uc.mem_write(0x20000,struct.pack('>'+'I'*(1+len(args)),0x10000,*args))
        uc.emu_start(sym[name],0x10000,count=100000)
        assert uc.reg_read(UC_M68K_REG_PC)==0x10000, (name,'did not return')
        assert uc.reg_read(UC_M68K_REG_A7)==0x20004, (name,'stack imbalance')
        return instructions[0]
    source = '#include <stdio.h>\n#include "modules/supersaw/engine.c"\nint main(void) {\n'
    source += 'struct ss_voice v; int16_t out[65];\n'
    for case in CASES:
        for n in COUNTS:
            source += 'v=(struct ss_voice){{'+','.join(str(p)+'u' for p in PHASES[:7])+'},'+str(PHASES[7])+'u};\n'
            source += '{struct ss_params p={'+','.join(str(p)+'u' for p in case)+'};'
            source += f'ss_render(&v,&p,out,{n});ss_render(&v,&p,out,{n});fwrite(out,2,{n},stdout);}}\n'
    source += 'return 0;}\n'
    with tempfile.TemporaryDirectory() as tmp:
        c,exe = Path(tmp)/'oracle.c',Path(tmp)/'oracle'; c.write_text(source)
        subprocess.run(['cc','-O2','-fsanitize=address,undefined','-I',str(ROOT),str(c),'-o',str(exe)],check=True)
        expected = struct.unpack(f'={sum(COUNTS)*len(CASES)}h',subprocess.check_output([str(exe)]))
    actual = []
    costs = []
    for case in CASES:
        for n in COUNTS:
            initial = struct.pack('>8I',*PHASES)+bytes(stride-32)
            uc.mem_write(0x24000,initial)
            uc.mem_write(0x25000,struct.pack('>IBBBB',*case))
            cold = call('ss_render',0x24000,0x25000,0x26000,n)
            warm = call('ss_render',0x24000,0x25000,0x26000,n)
            actual.extend(struct.unpack(f'>{n}h',bytes(uc.mem_read(0x26000,n*2))))
            if n == 0:
                assert bytes(uc.mem_read(0x24000,stride)) == initial, 'zero-length call changed state'
            if n == 16:
                # A regression budget for this generated engine, not a claim
                # about hardware cycles or the whole frame's CPU headroom.
                limit = 500 if case[1:] == (0,0,0,0) else 1150
                assert warm <= limit, ('render instruction regression',case,warm,limit)
            costs.append(dict(params=case,samples=n,cold_instructions=cold,warm_instructions=warm))
    assert tuple(actual)==expected, [(i,a,b) for i,(a,b) in enumerate(zip(actual,expected)) if a!=b][:10]
    (out/'receipt.json').write_text(json.dumps(dict(image_sha256=hashlib.sha256((ROOT/'out/mainos_bus.bin').read_bytes()).hexdigest(),
        exact_samples=len(actual),initialized_bytes=8+32+32+size+402,costs=costs,hardware_tested=False),indent=2)+'\n')
    print(f'[ok] linked ColdFire: initialized state, {len(actual)} exact host samples, split-call sizes, instruction budgets, phase wrap and extreme pitches')

if __name__=='__main__': main()
