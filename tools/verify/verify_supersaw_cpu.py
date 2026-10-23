#!/usr/bin/env python3
"""Profile actual linked ColdFire render paths, not host timings.

Reports executed instructions and multiply/divide counts. These are not
hardware cycles: caches, bus contention and the surrounding OS are excluded.
Pass --runtime to retain a reproducible baseline across rebuilds.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.m68k_const import (UC_CPU_M68K_CFV4E, UC_M68K_REG_A7, UC_M68K_REG_PC,
                               UC_M68K_REG_SR, UC_M68K_REG_A4, UC_M68K_REG_A5,
                               UC_M68K_REG_D0, UC_M68K_REG_D2)

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runtime', type=Path, default=ROOT/'out/platform/runtime')
    ap.add_argument('--output', type=Path, default=ROOT/'out/supersaw-cpu.json')
    args = ap.parse_args()
    elf = args.runtime/'runtime.elf'
    symbols = subprocess.check_output(['m68k-elf-nm', '-S', str(elf)], text=True)
    sym = {f[-1]: int(f[0], 16) for line in symbols.splitlines()
           if len(f := line.split()) in (3, 4)}
    dis = subprocess.check_output(['m68k-elf-objdump', '-d', str(elf)], text=True)
    op = {}; owner = {}; function = ''
    for line in dis.splitlines():
        if m := re.match(r'^[0-9a-f]+ <([^>]+)>:', line):
            function = m[1]
        if m := re.match(r'^\s*([0-9a-f]+):\s+(?:[0-9a-f]{4}\s+)+\s*([a-z][a-z0-9.]+)', line):
            at = int(m[1], 16); op[at] = m[2]; owner[at] = function
    headers = subprocess.check_output(['m68k-elf-objdump', '-h', str(elf)], text=True)
    base = int(next(line.split()[3] for line in headers.splitlines()
                    if len(line.split()) > 3 and line.split()[1] == '.text'), 16)
    data = (args.runtime/'runtime.bin').read_bytes()
    uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN); uc.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
    uc.mem_map(base & ~4095, (base % 4096 + len(data) + 4095) & ~4095)
    uc.mem_map(0x10000, 0x20000); uc.reg_write(UC_M68K_REG_SR, 0x2000)
    counts = Counter(); functions = Counter()
    def tick(_uc, address, _size, _user):
        counts[op.get(address, 'unknown')] += 1
        functions[owner.get(address, 'unknown')] += 1
    uc.hook_add(UC_HOOK_CODE, tick)
    def call(name, *values):
        counts.clear(); functions.clear()
        uc.reg_write(UC_M68K_REG_A7, 0x20000)
        uc.mem_write(0x20000, struct.pack('>'+'I'*(1+len(values)), 0x10000, *values))
        uc.emu_start(sym[name], 0x10000, count=100000)
        assert uc.reg_read(UC_M68K_REG_PC) == 0x10000, name
        assert uc.reg_read(UC_M68K_REG_A7) == 0x20004, 'stack imbalance'
        return dict(instructions=sum(counts.values()),
                    multiplies=sum(n for k,n in counts.items() if k.startswith('mul')),
                    # binutils prints ColdFire long division as remsl when
                    # quotient/remainder register fields coincide.
                    divides=sum(n for k,n in counts.items() if k.startswith(('div','rem'))),
                    functions=dict(functions))
    cases = []
    for voices in (0, 1, 2, 3, 4):  # 0 = native mono path, 1 = one poly voice
        for typ in (0, 1, 2, 3):
            for setting, sub, drive, amount in (('plain',0,0,0), ('rich',96,80,80)):
                uc.mem_write(base, data)
                uc.mem_write(sym['ss_active'], b'\x01'+bytes(7))
                uc.mem_write(sym['ss_setup'], bytes((64,64,amount,64,typ,83)))
                state = bytearray(128); state[80] = int(bool(voices))
                struct.pack_into('>I', state, 12, 21426141)
                struct.pack_into('>I', state, 24, 32767)
                struct.pack_into('>H', state, 38, 32767)
                uc.mem_write(0x24000, bytes(state))
                uc.mem_write(0x25000, struct.pack('>6H', 16384,96<<8,64<<8,64<<8,sub<<8,drive<<8))
                pool = bytearray(256)
                for v in range(voices):
                    struct.pack_into('>I', pool, v*64+12, 21426141*(v+1))
                    struct.pack_into('>I', pool, v*64+24, 32767)
                    struct.pack_into('>I', pool, v*64+48, v+1)
                    struct.pack_into('>H', pool, v*64+60, 32767)
                    pool[v*64+36] = 1
                uc.mem_write(0x27000, bytes(pool))
                cold = call('ss_track_fill',0,0x24000,0x25000,0x26000,16,0x27000)
                for _ in range(12):
                    warm = call('ss_track_fill',0,0x24000,0x25000,0x26000,16,0x27000)
                uc.mem_write(0x25006, struct.pack('>H', 32<<8))
                changed = call('ss_track_fill',0,0x24000,0x25000,0x26000,16,0x27000)
                uc.mem_write(0x24000+12,struct.pack('>I',21427141))
                for v in range(voices):
                    uc.mem_write(0x27000+v*64+12,struct.pack('>I',21427141*(v+1)))
                pitch = call('ss_track_fill',0,0x24000,0x25000,0x26000,16,0x27000)
                ramps={}
                for phase,previous,target in (('attack',0,16384),('release',16384,0),('silent_tail',0,0)):
                    uc.mem_write(0x24000+24,struct.pack('>I',target))
                    uc.mem_write(0x24000+38,struct.pack('>H',previous))
                    for v in range(voices):
                        uc.mem_write(0x27000+v*64+24,struct.pack('>I',target))
                        uc.mem_write(0x27000+v*64+60,struct.pack('>H',previous))
                    ramps[phase]=call('ss_track_fill',0,0x24000,0x25000,0x26000,16,0x27000)
                cases.append(dict(voices=voices, type=typ, setting=setting,
                                  cold=cold, warm=warm, cutoff_change=changed,pitch_change=pitch,**ramps))
    # Control work outside the audio renderer: fine/Part refresh and the
    # native per-track parameter preparation up to the AMP release branch.
    uc.mem_map(0x10000000,0x200000);uc.mem_map(0x46000000,0x1100000)
    uc.mem_map(0x80000000,0x10000)
    uc.mem_write(base,data);uc.mem_write(sym['ss_active'],b'\x01')
    uc.mem_write(0x46c82456,struct.pack('>I',0x47000000))
    uc.mem_write(0x4708ed80+0x1ec,bytes((76,64,80,64,1,83)))
    fine=call('ss_fine',0,16384)
    assert uc.reg_read(UC_M68K_REG_D0)==76<<8
    uc.reg_write(UC_M68K_REG_D2,0);uc.reg_write(UC_M68K_REG_A4,0x25000)
    uc.reg_write(UC_M68K_REG_A5,0x24000);uc.mem_write(0x24000,bytes(128))
    uc.mem_write(0x80000810+14,b'\x0a')
    counts.clear();functions.clear()
    uc.emu_start(sym['po_fr_params'],sym['po_fr_rk'],count=10000)
    assert uc.reg_read(UC_M68K_REG_PC)==sym['po_fr_rk']
    native=dict(instructions=sum(counts.values()),release_coefficient=uc.reg_read(UC_M68K_REG_D0),
                multiplies=sum(v for k,v in counts.items() if k.startswith('mul')),
                divides=sum(v for k,v in counts.items() if k.startswith(('div','rem'))))
    receipt = dict(runtime_sha256=hashlib.sha256(data).hexdigest(), samples_per_call=16,
                   hardware_cycles=False, cases=cases, fine_control=fine, native_poly_parameters=native)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2)+'\n')
    for c in cases:
        if c['voices'] in (0,4):
            print(c['voices'],c['type'],c['setting'],c['warm']['instructions'],
                  'mul',c['warm']['multiplies'],'div',c['warm']['divides'])
    print('fine',fine['instructions'],'native parameters',native)


if __name__ == '__main__':
    main()
