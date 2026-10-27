#!/usr/bin/env python3
"""Compare two linked Supersaw runtimes over changing native frame inputs.

This is sample/state equivalence, not hardware timing. The frozen baseline
must have the same private voice/filter layouts as the candidate.
Requires the repository's corrected Unicorn; the EMAC self-test fails closed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import struct
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import toolpath
from emu_bringup import emac_selftest
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN
from unicorn.m68k_const import UC_CPU_M68K_CFV4E, UC_M68K_REG_A7, UC_M68K_REG_PC, UC_M68K_REG_SR
STATE,PARAMS,OUTPUT,POOL=0x24000,0x25000,0x26000,0x27000

class Runtime:
    def __init__(self,path):
        elf=path/'runtime.elf'
        self.symbols={};self.sizes={}
        for line in subprocess.check_output(['m68k-elf-nm','-S',str(elf)],text=True).splitlines():
            f=line.split()
            if len(f) in (3,4): self.symbols[f[-1]]=int(f[0],16)
            if len(f)==4:self.sizes[f[-1]]=int(f[1],16)
        headers=subprocess.check_output(['m68k-elf-objdump','-h',str(elf)],text=True)
        base=int(next(l.split()[3] for l in headers.splitlines() if len(l.split())>3 and l.split()[1]=='.text'),16)
        data=(path/'runtime.bin').read_bytes();self.sha256=hashlib.sha256(data).hexdigest()
        self.base,self.data=base,data
        self.uc=Uc(UC_ARCH_M68K,UC_MODE_BIG_ENDIAN);self.uc.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
        self.uc.mem_map(base&~4095,(base%4096+len(data)+4095)&~4095)
        self.uc.mem_write(base,data);self.uc.mem_map(0x10000,0x20000)
        self.uc.reg_write(UC_M68K_REG_SR,0x2000)
        self.uc.mem_write(self.symbols['ss_active'],bytes([1]*8))
    def reset(self):
        self.uc.mem_write(self.base,self.data)
        self.uc.mem_write(STATE,bytes(0x4000))
        self.uc.mem_write(self.symbols['ss_active'],bytes([1]*8))
    def call(self,name,*args):
        self.uc.reg_write(UC_M68K_REG_A7,0x20000)
        self.uc.mem_write(0x20000,struct.pack('>'+'I'*(1+len(args)),0x10000,*args))
        self.uc.emu_start(self.symbols[name],0x10000,count=200000)
        assert self.uc.reg_read(UC_M68K_REG_PC)==0x10000,name
        assert self.uc.reg_read(UC_M68K_REG_A7)==0x20004,'stack imbalance'
    def read(self,address,size):return bytes(self.uc.mem_read(address,size))

def deterministic(a,b,names):
    """Dwell in the fast paths, then leave them without losing hidden state.

    Randomizing every input on every call misses warm coefficient caches,
    fully wet fixed filters and held AMP. These segments retain real note
    identity while toggling features, including ENV after elapsed ENV=0 time.
    """
    scenarios=[]
    phases=(('attack_hold',24),('one_lsb_gain',16),('zero_gain',16),
            ('retrigger',16),('mixed_envelopes',24),('cutoff_ramp',32),
            ('neutral_open',16),('filter_resume',16),('env_enable',16),
            ('features_off',16),('features_resume',16),('release_retire',16))
    for label,typ,sub,drive,layout,split in (
            ('mono_unity_dry',0,0,0,'mono',False),
            ('sparse_sub_only',0,96,0,'sparse',False),
            ('sparse_drive_only',0,0,80,'sparse',False),
            ('mixed_mono_triad',0,96,80,'mixed',False),
            ('dual_low',1,96,80,'dual',False),
            ('dual_bp',2,96,80,'dual',False),
            ('dual_hp',3,96,80,'dual',False),
            ('mixed_split_low',1,96,80,'mixed',True)):
        for r in (a,b):r.reset()
        tracks=(5,6) if layout=='mixed' else (2,3) if layout=='dual' else (3,)
        total=0;calls=0;stamps={t:1 for t in tracks};phase_counts={}
        for phase,frames in phases:
            phase_counts[phase]=0
            if phase=='retrigger':
                for t in tracks:stamps[t]+=1
            for frame in range(frames):
                for track in tracks:
                    mono=layout=='mono' or (layout=='mixed' and track==tracks[0])
                    slots=() if mono else (1,3) if layout=='sparse' else (0,2,3) if layout=='mixed' else (0,1,2,3)
                    state=bytearray(a.read(STATE+track*128,128));pool=bytearray(a.read(POOL+track*256,256))
                    state[80]=int(not mono)
                    struct.pack_into('>I',state,12,21426141+track*1973)
                    level=32768 if mono else 32767
                    if phase=='one_lsb_gain':level=1
                    elif phase in ('zero_gain','release_retire'):level=0
                    elif phase!='attack_hold':level=20000
                    struct.pack_into('>I',state,24,level)
                    for v in range(4):
                        active=v in slots and not(phase=='release_retire' and frame>=8)
                        pool[v*64+36]=int(active)
                        struct.pack_into('>I',pool,v*64+12,21426141*(v+1)+track*1973)
                        target=level
                        if phase=='mixed_envelopes':
                            # One held, one changing, one releasing and one
                            # zero-to-zero lane, including noncontiguous pools.
                            target=(20000,frame*700, max(0,20000-frame*1000),0)[v]
                        struct.pack_into('>I',pool,v*64+24,target)
                        struct.pack_into('>I',pool,v*64+48,stamps[track]+v)
                    cutoff=24+(frame*7)%104 if phase=='cutoff_ramp' else 127 if phase=='neutral_open' else 64
                    resonance=0 if phase=='neutral_open' else 84
                    amount=80 if phase=='env_enable' else 0
                    use_sub,use_drive=(0,0) if phase=='features_off' else (sub,drive)
                    fp=struct.pack('>6H',16384,96<<8,64<<8,cutoff<<8,use_sub<<8,use_drive<<8)
                    setup=bytes((64,resonance,amount,64,typ,83))
                    n=(1,15,16,7,9,32,0)[calls%7] if split else 16
                    context=(label,phase,frame,track,n)
                    for r in (a,b):
                        r.uc.mem_write(STATE+track*128,bytes(state));r.uc.mem_write(POOL+track*256,bytes(pool))
                        r.uc.mem_write(PARAMS,fp);r.uc.mem_write(r.symbols['ss_setup']+track*6,setup)
                        r.uc.mem_write(r.symbols['ss_note_stamp']+track*4,struct.pack('>I',stamps[track]))
                        r.uc.mem_write(OUTPUT,b'\xa5'*264)
                        r.call('ss_track_fill',track,STATE+track*128,PARAMS,OUTPUT,n,POOL+track*256)
                    assert a.read(OUTPUT,264)==b.read(OUTPUT,264),('deterministic audio/guard',context)
                    assert a.read(STATE,1024)==b.read(STATE,1024),('deterministic mono gains',context)
                    assert a.read(POOL,2048)==b.read(POOL,2048),('deterministic poly gains',context)
                    for name in names:
                        assert a.read(a.symbols[name],a.sizes[name])==b.read(b.symbols[name],b.sizes[name]),(name,context)
                    total+=2*n;calls+=1;phase_counts[phase]+=1
        scenarios.append(dict(scenario=label,blocks=calls,exact_stereo_samples=total,phases=phase_counts))
    return scenarios

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline-runtime',required=True,type=Path)
    ap.add_argument('--runtime',type=Path,default=ROOT/'out/platform/runtime')
    ap.add_argument('--output',type=Path,default=ROOT/'out/supersaw-equivalence.json')
    ap.add_argument('--blocks',type=int,default=1600)
    args=ap.parse_args()
    emac_ok,emac_detail=emac_selftest()
    assert emac_ok,emac_detail
    a,b=Runtime(args.baseline_runtime),Runtime(args.runtime)
    names=['ss_voices','ss_poly_voices','ss_filters','ss_samples','ss_poly_samples','ss_filter_samples','ss_unsupported']
    for name in names:assert a.sizes[name]==b.sizes[name],('layout changed',name)
    rng=random.Random(0x53533131);samples=0;native=0;carry=0
    for block in range(args.blocks):
        track=block%8;n=16 if block%3 else rng.randrange(33);native+=n==16
        state=bytearray(a.read(STATE+track*128,128));pool=bytearray(a.read(POOL+track*256,256))
        state[80]=int(block%11!=0)
        struct.pack_into('>I',state,12,rng.getrandbits(32))
        target=rng.choice([0,1,32767,32768,rng.randrange(32769)])
        struct.pack_into('>I',state,24,target)
        if block%7==0:struct.pack_into('>H',state,38,0)
        for v in range(4):
            pool[v*64+36]=rng.randrange(4)
            struct.pack_into('>I',pool,v*64+12,rng.getrandbits(32))
            prev=int.from_bytes(pool[v*64+60:v*64+62],'big')
            struct.pack_into('>I',pool,v*64+24,rng.choice([0,1,32767,prev,rng.randrange(32768)]))
            struct.pack_into('>I',pool,v*64+48,block//9+v)
            if block%5==0:struct.pack_into('>H',pool,v*64+60,0)
        fp=struct.pack('>6H',16384,*[rng.randrange(128)<<8 for _ in range(5)])
        setup=bytes([64,*[rng.randrange(128) for _ in range(3)],block%4,83])
        for r in (a,b):
            r.uc.mem_write(STATE+track*128,bytes(state));r.uc.mem_write(POOL+track*256,bytes(pool))
            r.uc.mem_write(PARAMS,fp);r.uc.mem_write(r.symbols['ss_setup']+track*6,setup)
            r.uc.mem_write(OUTPUT,b'\xa5'*264)
            r.call('ss_track_fill',track,STATE+track*128,PARAMS,OUTPUT,n,POOL+track*256)
        assert a.read(OUTPUT,264)==b.read(OUTPUT,264),('audio/guard mismatch',block,n)
        assert a.read(STATE,1024)==b.read(STATE,1024),('mono gain mismatch',block)
        assert a.read(POOL,2048)==b.read(POOL,2048),('poly gain mismatch',block)
        for name in names:
            assert a.read(a.symbols[name],a.sizes[name])==b.read(b.symbols[name],b.sizes[name]),(name,block,n)
        if block%17==0:
            for r in (a,b):r.call('ss_carry',track,block%4,block)
            carry+=1
        samples+=n
    scenarios=deterministic(a,b,names)
    deterministic_blocks=sum(s['blocks'] for s in scenarios)
    deterministic_samples=sum(s['exact_stereo_samples'] for s in scenarios)
    result=dict(baseline_runtime_sha256=a.sha256,runtime_sha256=b.sha256,blocks=args.blocks,
                native_size_blocks=native,mono_to_poly_carries=carry,exact_stereo_samples=2*samples,
                deterministic_scenarios=scenarios,deterministic_blocks=deterministic_blocks,
                total_blocks=args.blocks+deterministic_blocks,total_exact_stereo_samples=2*samples+deterministic_samples,
                compared_state=names,hardware_timing=False,emac_selftest=emac_detail)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(f'[ok] {args.blocks} linked A/B blocks: {2*samples} exact stereo samples, voice/filter/gain state and output guards')
    print(f'[ok] {deterministic_blocks} deterministic linked A/B blocks: {deterministic_samples} exact stereo samples across {len(scenarios)} sustained/transition scenarios')
if __name__=='__main__':main()
