#!/usr/bin/env python3
"""Exact native pitch-cache and optional diagnostic ABI checks.

Requires the repository's corrected Unicorn (scripts/build_unicorn.sh),
or LIBUNICORN_PATH pointing at an isolated build of it. Counts instructions,
never hardware cycles. Native pitch arithmetic is executed as the oracle.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import toolpath
from emu_bringup import emac_selftest
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.m68k_const import (UC_CPU_M68K_CFV4E, UC_M68K_REG_A7,
    UC_M68K_REG_PC, UC_M68K_REG_SR, UC_M68K_REG_D0, UC_M68K_REG_D2,
    UC_M68K_REG_D5, UC_M68K_REG_D6, UC_M68K_REG_A4)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runtime',type=Path,default=ROOT/'out/platform/runtime')
    ap.add_argument('--output',type=Path,default=ROOT/'out/supersaw-lifecycle.json')
    args=ap.parse_args()
    ok,detail=emac_selftest()
    assert ok,detail
    elf=args.runtime/'runtime.elf'
    nm=subprocess.check_output(['m68k-elf-nm',str(elf)],text=True)
    sym={f[-1]:int(f[0],16) for line in nm.splitlines() if len(f:=line.split())==3}
    headers=subprocess.check_output(['m68k-elf-objdump','-h',str(elf)],text=True)
    base=int(next(s.split()[3] for s in headers.splitlines()
        if len(s.split())>3 and s.split()[1]=='.text'),16)
    data=(args.runtime/'runtime.bin').read_bytes()
    uc=Uc(UC_ARCH_M68K,UC_MODE_BIG_ENDIAN);uc.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
    uc.mem_map(base&~4095,(base%4096+len(data)+4095)&~4095);uc.mem_write(base,data)
    stock=(ROOT/'out/raw/section_3_MAIN_OS.bin').read_bytes()
    uc.mem_map(0x40000000,(len(stock)+4095)&~4095);uc.mem_write(0x40000000,stock)
    uc.mem_map(0x10000,0x20000);uc.reg_write(UC_M68K_REG_SR,0x2000)
    uc.mem_write(0x10100,bytes.fromhex('a93c000000204e75')) # fractional MACSR, rts
    count=[0]
    def tick(*_):count[0]+=1
    uc.hook_add(UC_HOOK_CODE,tick)
    def call(name,*args):
        uc.reg_write(UC_M68K_REG_A7,0x20000)
        uc.mem_write(0x20000,struct.pack('>'+'I'*(1+len(args)),0x10000,*args))
        count[0]=0
        uc.emu_start(sym[name] if isinstance(name,str) else name,0x10000,count=100000)
        assert uc.reg_read(UC_M68K_REG_PC)==0x10000,name
        assert uc.reg_read(UC_M68K_REG_A7)==0x20004,'stack imbalance'
        return uc.reg_read(UC_M68K_REG_D0),count[0]
    call(0x10100)
    uc.reg_write(UC_M68K_REG_A4,0x24000)
    assert bytes(uc.mem_read(sym['ss_pitch_cache'],384))==bytes(384),'uninitialized pitch cache'
    rng=random.Random(917)
    words=[-100000,0,0x400,0x4000,0x7c00,130000]
    words += list(range(-66000,100000,127))+[rng.randrange(-66000,100000) for _ in range(500)]
    rows=[]
    for i,word in enumerate(words):
        track=i%8
        uc.reg_write(UC_M68K_REG_D2,track)
        uc.reg_write(UC_M68K_REG_D6,word&0xffffffff)
        uc.reg_write(UC_M68K_REG_D5,0x12345678)
        uc.mem_write(0x2401b,bytes((i%2,))) # RATE mode cannot affect folded synth pitch
        expected,native=call('po_rate_fold')
        uc.mem_write(sym['ss_active']+track,b'\x01')
        cold,cost=call('ss_pitch_rate')
        warm,hit=call('ss_pitch_rate')
        assert cold==warm==expected,(word,expected,cold,warm)
        assert hit< native,(word,hit,native)
        assert uc.reg_read(UC_M68K_REG_D6)==word&0xffffffff
        assert uc.reg_read(UC_M68K_REG_D5)==0x12345678
        uc.mem_write(sym['ss_active']+track,b'\x00')
        fallback,_=call('ss_pitch_rate');assert fallback==expected
        rows.append((native,cost,hit))
    # A colliding different pitch must replace the entry, never reuse its value.
    for word in (0x4000,0x6000,0x4000,0x4001,0x4000):
        uc.reg_write(UC_M68K_REG_D6,word)
        uc.mem_write(sym['ss_active']+track,b'\x01')
        assert call('ss_pitch_rate')[0]==call('po_rate_fold')[0]
    result=dict(runtime_sha256=hashlib.sha256(data).hexdigest(),hardware_cycles=False,
        exact_pitch_cases=len(words),native_mean=sum(r[0] for r in rows)/len(rows),
        miss_or_hit_mean=sum(r[1] for r in rows)/len(rows),hit_instructions=sorted(set(r[2] for r in rows)))
    if 'ss_diag_events' in sym:
        uc.mem_map(0xfc07c000,4096)
        uc.mem_write(0xfc07c00c,struct.pack('>I',100))
        uc.mem_write(sym['ss_native_clock']+12,struct.pack('>I',42))
        event_cost=[]
        for k in range(150):
            _,n=call('ss_diag_event',3,1,72);event_cost.append(n)
        assert int.from_bytes(uc.mem_read(sym['ss_diag_sequence'],4),'big')==150
        assert bytes(uc.mem_read(sym['ss_diag_sequence']+4,4))==bytes(4)
        event=struct.unpack('>8I',uc.mem_read(sym['ss_diag_events']+(150&63)*32,32))
        assert event[:6]==(150,42,100,1,3,72),event
        call('ss_diag_event',3,4,0)
        uc.mem_write(0xfc07c00c,struct.pack('>I',400))
        call('ss_diag_event',3,5,0)
        costs=struct.unpack('>4I',uc.mem_read(sym['ss_diag_costs']+(3*3+2)*16,16))
        assert costs==(1,300,300,300),costs
        state=bytearray(128);state[80]=1
        uc.mem_write(0x24000,bytes(state));uc.mem_write(0x25000,bytes(12))
        uc.mem_write(0x27000,bytes(256));uc.mem_write(sym['ss_active']+3,b'\x01')
        call_args=(3,0x24000,0x25000,0x26000,16,0x27000)
        _,plain=call('ss_track_fill_impl',*call_args)
        _,observed=call('ss_track_fill',*call_args)
        snap=struct.unpack('>28I',uc.mem_read(sym['ss_diag_tracks']+3*112,112))
        assert snap[:7]==(2,42,16,1,1,0,0),snap
        assert not any(snap[7:]),snap
        result['diagnostics']=dict(event_instructions=max(event_cost),
            silent_render_observation_overhead=observed-plain,ring_wrap=True,snapshot=True)
    else:
        assert not any(n.startswith('ss_diag_') for n in sym),'diagnostics in production'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
