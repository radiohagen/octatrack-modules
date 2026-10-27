#!/usr/bin/env python3
"""Exact native pitch-cache and optional diagnostic ABI checks.

Requires the repository's corrected Unicorn (scripts/build_unicorn.sh),
or LIBUNICORN_PATH pointing at an isolated build of it. Counts instructions,
never hardware cycles. Native pitch arithmetic is executed as the oracle.
"""
import argparse
import hashlib
import json
import math
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
    UC_M68K_REG_D5, UC_M68K_REG_D6, UC_M68K_REG_A2, UC_M68K_REG_A4)


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
    # Section 3 starts at 0x40000400; mapping it at the page boundary reads
    # the wrong pitch table while cached-versus-native comparisons still pass.
    stock_base=0x40000400
    uc.mem_map(0x40000000,(len(stock)+0x400+4095)&~4095)
    uc.mem_write(stock_base,stock)
    assert bytes(uc.mem_read(0x400aa294+512*4,4))==struct.pack('>I',0x08000000), 'stock pitch-table origin'
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
    # Independent equal-temperament oracle: exact cache parity alone cannot
    # catch a misplaced stock image or an incorrect native pitch convention.
    # Raw 64 is sounding C4; native MIDI IN assigns note 84 to that raw byte.
    pitch_rows=[]
    for raw in range(128):
        semitones=raw-64
        uc.reg_write(UC_M68K_REG_D6,(0x4000+semitones*0x500)&0xffffffff)
        increment,_=call('po_rate_fold')
        assert call('ss_pitch_rate')[0]==increment
        frequency=increment*44100/(1<<32)
        expected=440*2**((semitones-9)/12)
        cents=1200*math.log2(frequency/expected)
        assert abs(cents)<.02,(raw,frequency,expected,cents)
        if pitch_rows:
            step=1200*math.log2(frequency/pitch_rows[-1]['frequency_hz'])
            assert abs(step-100)<.02,(raw,step)
        pitch_rows.append(dict(raw=raw,sounding_midi_note=raw-4,
            native_midi_note=raw+20 if raw+20<=127 else None,
            increment=increment,frequency_hz=frequency,cents_error=cents))

    # Execute the linked chromatic entry, including its synth-marker lookup,
    # then native word conversion and pitch cache. This fixture is memory-only:
    # it does not boot a device or claim front-panel/audio hardware acceptance.
    # QUANTIZER is an optional composition, not a SUPERSAW dependency.
    missing=[name for name in ('qz_chrom','qz_oct','qz_scale') if name not in sym]
    chromatic_cases=0
    chromatic_skipped_reason=(
        'QUANTIZER chromatic fixture unavailable; missing runtime symbols: '+', '.join(missing)
        if missing else None)
    if not missing:
        uc.mem_map(0x100b1000,0x4000)
        uc.mem_map(0x46000000,0x100000)
        uc.mem_map(0x46c82000,0x1000)
        uc.mem_map(0x80000000,0x1000)
        uc.mem_write(0x46c82456,struct.pack('>I',0x46000000))
        uc.mem_write(sym['qz_scale'],b'\0')
        for track in (2,3):
            uc.mem_write(0x46000000+0x8eda2+track,b'\1') # FLEX
            uc.mem_write(0x46000000+0x8f04b+track*5,bytes((track,)))
            uc.mem_write(0x100b14f0+track*0x448,b'FMSYNTH-SUPERSAW.wav\0')
            uc.mem_write(0x46000000+0x8ed80+0x1da+18+track*30,bytes((64,0,0,64,0,83)))
            uc.mem_write(sym['ss_active']+track,b'\1')
            uc.reg_write(UC_M68K_REG_D2,track)
            for octave in range(-4,5):
                uc.mem_write(sym['qz_oct'],bytes((octave&255,)))
                for key in range(16):
                    uc.reg_write(UC_M68K_REG_A2,key)
                    call('qz_chrom')
                    raw=uc.reg_read(UC_M68K_REG_A2)
                    assert raw==64+key-12+12*octave,(track,octave,key,raw)
                    uc.mem_write(0x24000,struct.pack('>H',raw<<8))
                    call('sy_word')
                    assert uc.reg_read(UC_M68K_REG_D6)==(0x4000+(raw-64)*0x500)&0xffffffff
                    assert call('ss_pitch_rate')[0]==pitch_rows[raw]['increment']
                    chromatic_cases+=1
    result=dict(runtime_sha256=hashlib.sha256(data).hexdigest(),hardware_cycles=False,
        exact_pitch_cases=len(words),native_mean=sum(r[0] for r in rows)/len(rows),
        miss_or_hit_mean=sum(r[1] for r in rows)/len(rows),hit_instructions=sorted(set(r[2] for r in rows)),
        stock_load_address=hex(stock_base),stock_sha256=hashlib.sha256(stock).hexdigest(),
        pitch_validation=dict(equal_tempered_cases=len(pitch_rows),
            max_absolute_cents_error=max(abs(r['cents_error']) for r in pitch_rows),
            chromatic_cases=chromatic_cases,chromatic_tracks=[3,4] if chromatic_cases else [],
            chromatic_skipped_reason=chromatic_skipped_reason,scale='OFF' if chromatic_cases else None,
            e_f_pairs=[pitch_rows[raw:raw+2] for raw in range(128-1) if (raw-64)%12==4],
            scope='Linked ColdFire chromatic entry and pitch conversion; no hardware timing or audio acceptance'))
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
