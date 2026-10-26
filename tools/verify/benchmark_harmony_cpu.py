#!/usr/bin/env python3
"""Opt-in HARMONY linked ColdFire instruction benchmarks, never hardware cycle claims.

Build a MIDI remix first. --artifacts accepts a frozen out/ layout so the
same fixtures can compare the exact baseline and candidate firmware bytes.
--compare refuses changed result digests; normal verification remains separate.
"""
import argparse
import bisect
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
from unicorn import UC_HOOK_CODE
from unicorn.m68k_const import *
from midi_machine import Machine, ROOT, InterruptMaskTrace
import harmony_retained as retained

BANK, STRIDE = 0x400e21e0, 0x9b340


class CpuMachine(Machine):
    def __init__(self, out):
        nm = subprocess.check_output(['m68k-elf-nm',str(out/'platform/runtime/runtime.elf')],text=True)
        rows = [line.split() for line in nm.splitlines()]
        symbols = {f[2]:int(f[0],16) for f in rows if len(f)==3}
        # C-local names can collide with another linked unit. These event
        # arrays are BSS; Follow also has a data symbol called pending.
        for name in ('staged','pending','fired','revision','bank_revision'):
            matches=[int(f[0],16) for f in rows if len(f)==3 and f[1]=='b' and f[2]==name]
            assert len(matches)==1,(name,matches)
            symbols[name]=matches[0]
        self.labels = sorted((int(f[0],16),f[2]) for f in rows if len(f)==3 and f[1] in ('T','t'))
        self.addresses = [a for a,_ in self.labels]
        super().__init__(lambda:symbols,artifact_root=out)
        self.initial_sr = 0x2000
        self.call('store_part_activate',stop=0x4000f938)
        self.call('ch_lock_init')
        self.uc.mem_write(BANK,b'\xff'*STRIDE)
        for pattern in range(16): self.put(BANK+pattern*0x8ed8+0x8e57,0)
        for part in range(8):
            base = BANK+(0x8ed80+part*0x18b2 if part<4 else 0x9504a+(part-4)*0x18b2)
            self.uc.mem_write(base+0x1712,bytes(288))
            for t in range(8):
                self.put(base+0x3e2+t*32,60)
                for field,value in ((3,0),(5,0),(12,0),(13,35),(15,3),(16,0),(17,1),(18,0),(19,42)):
                    self.put(base+0x4e2+t*36+field,value)
        for t in range(8):
            self.put(0x46c76df1+68*t,1)
            self.put(0x46c76fe0+32*t,60)
            self.put(0x46c76fec+32*t,64)
            self.put(0x8000666e+t,0); self.put(0x80006676+t,0)
        self.put(0x80001828,0); self.put(0x80001829,0)
        self.call('hd_bank_loaded',0)

    def put(self,address,value,n=1): self.uc.mem_write(address,(value&((1<<(n*8))-1)).to_bytes(n,'big'))
    def c(self,name,*args):
        self.uc.mem_write(self.stack+4,b''.join((v&0xffffffff).to_bytes(4,'big') for v in args))
        result=self.call(name)
        assert self.uc.reg_read(UC_M68K_REG_A7)==self.stack+4,name
        return result
    def mode(self,value):
        for t in range(8): self.put(self.part_address(t,5),value)
    def instruction_limit(self,name): return 30000000
    def profile(self,run):
        counts=Counter(); trace=InterruptMaskTrace(self.uc,ipl=0)
        masked=peak=0
        def count(u,pc,size,user):
            nonlocal masked,peak
            if pc in self.stops:return
            counts[pc]+=1
            old=trace.before(pc)
            if old or trace.ipl: masked+=1; peak=max(peak,masked)
            else: masked=0
        hook=self.uc.hook_add(UC_HOOK_CODE,count)
        try: result=run()
        finally: self.uc.hook_del(hook)
        by_name=Counter()
        for pc,n in counts.items():
            i=bisect.bisect_right(self.addresses,pc)-1
            name=self.labels[i][1] if i>=0 and pc>=self.base else 'native'
            by_name[name]+=n
        encoded=json.dumps(result,sort_keys=True,separators=(',',':')).encode()
        return sum(counts.values()),peak,hashlib.sha256(encoded).hexdigest(),by_name.most_common(8)


def event_state(m):
    return {name:bytes(m.uc.mem_read(m.sym[name],size)).hex()
            for name,size in (('staged',128),('pending',512),('fired',128),('hd_rebuild',8))}

def event_call(m,name,*args):
    m.c(name,*args)
    return event_state(m)

def observation_state(m):
    # Host reads add no guest instructions. Include the native bank and its
    # SRAM mirror so a no-op observer cannot silently rewrite NOTE bytes,
    # Part data, dirty flags or the retained commit words.
    state = {name:bytes(m.uc.mem_read(m.sym[name],size)).hex()
             for name,size in (('hd_banks',128*131),('revision',128*4),
                               ('bank_revision',4),('ch_lock_status',1))}
    state['native_bank'] = bytes(m.uc.mem_read(BANK,STRIDE)).hex()
    state['live_bank'] = bytes(m.uc.mem_read(0x1001614e,STRIDE)).hex()
    return state


def observe(m):
    before = observation_state(m)
    m.c('hd_ui_observe_c')
    after = observation_state(m)
    assert after == before, 'reconciled UI observation mutated bank state'
    return after


def cases(m):
    u,s=m.uc,m.sym
    for scale in (0,320,428):
        yield f'harmony/decode_{scale}_84_degrees',lambda scale=scale:[m.call('hd_decode',d,scale) for d in range(84)]
        yield f'harmony/encode_{scale}_128_notes',lambda scale=scale:[m.call('hd_encode',n,scale) for n in range(128)]
    for mode in (0,1,2):
        m.mode(mode)
        for t in range(8): m.c('hd_sync_c',0,0,t)
        yield f'harmony/stage_mode_{mode}_8_tracks',lambda:[event_call(m,'hd_event_stage_c',0,0,t,0,0) for t in range(8)]
        yield f'harmony/ui_observe_mode_{mode}',lambda:observe(m)
        for t in range(8):m.c('hd_event_fire_c',t,t)
        yield f'harmony/tick_mode_{mode}_8_tracks',lambda:[event_call(m,'hd_event_tick_c',t) for t in range(8)]
        yield f'harmony/prepare_mode_{mode}_8_tracks',lambda:[m.c('hd_prepare_c',60,t) for t in range(8)]
        def generate():
            result=[]
            for t in range(8):
                u.mem_write(m.scratch,bytes((60,11,12,13)))
                m.call('mh_generate',t,0,a0=m.scratch)
                result.append(bytes(u.mem_read(m.scratch,4)).hex())
            return result
        yield f'harmony/generate_mode_{mode}_8_tracks',generate
    m.mode(2)
    for auto in (0,1):
        m.call('mh_voic_set',0,auto)
        def progression():
            result=[]
            for pitches in ((60,64,67,60),(62,65,69,62),(67,71,74,67),(60,64,67,60)):
                u.mem_write(m.scratch,bytes(pitches));m.call('mh_voice',0,a0=m.scratch)
                result.append(bytes(u.mem_read(m.scratch,4)).hex())
            return result
        yield f'harmony/voicing_{auto}_4_chords',progression
    m.mode(2)
    for scale in (0,1,2,25,84):
        m.set_key(0,scale)
        yield f'harmony/quant_key_{scale}_128_notes',lambda:[m.call('mh_quant_at',n,0,regs={UC_M68K_REG_D2:0}) for n in range(128)]
    m.set_key(0,1)
    for spread in range(3):
        def spacing(spread=spread):
            result=[]
            for notes,count in (((60,64,67,60),3),((60,64,67,71),4),((112,116,119,112),3)):
                u.mem_write(m.scratch,bytes(notes))
                ok=m.call('mh_spread',spread,a0=m.scratch,regs={UC_M68K_REG_D6:count})
                result.append((ok,bytes(u.mem_read(m.scratch,4)).hex()))
            return result
        yield f'harmony/spread_{spread}_3_chords',spacing
    for boundary in range(4):
        def accum(boundary=boundary):
            m.c('ha_bank_reset_c',0)
            m.c('ha_runtime_reset_c')
            u.mem_write(s['ha_lanes']+32,bytes((253,3,boundary,3,10)))
            result=[]
            for i in range(24):
                m.c('ha_fire_c',0,0,0,0)
                result.append(m.c('ha_shift_c',60,0,0))
                m.c('ha_sounded_c',0)
                # Repeated arp notes must retain the captured offset.
                result.append(m.c('ha_shift_c',60,0,0))
                m.c('ha_sounded_c',0)
            return result
        yield f'harmony/accumulator_boundary_{boundary}_24_events',accum
    for size in (1,2,3):
        for auto in (0,1):
            m.call('mh_size_set',0,size)
            m.call('mh_voic_set',0,auto)
            for spread in range(3):
                m.call('mh_sprd_set',0,spread)
                def fixed_size():
                    result=[]
                    for pitch in (60,62,67,60):
                        u.mem_write(m.scratch,bytes((pitch,)*4))
                        result.append(m.call('mh_generate',0,0,a0=m.scratch))
                        m.call('mh_voice',0,a0=m.scratch)
                        result.append(bytes(u.mem_read(m.scratch,4)).hex())
                    return result
                yield f'harmony/size_{size}_voice_{auto}_spread_{spread}',fixed_size
    # Initialized OFF, sparse HARM and fully locked HARM current banks.
    for name,density in (('empty',0),('sparse',8),('dense',8192)):
        roots=bytearray();qualities=bytearray()
        for lane in range(128):
            degrees=[(lane*64+i)%84 if lane*64+i<density else 255 for i in range(64)]
            notes=[255 if d==255 else max(0,min(127,(d//7-1)*12+(0,2,4,5,7,9,11)[d%7])) for d in degrees]
            roots.extend(bytes(degrees+notes+[2 if density else 1,0,255]))
            qualities.extend(bytes((i+lane)%8 if lane*64+i<density else 255 for i in range(64)))
        u.mem_write(s['hd_banks'],bytes(roots));u.mem_write(s['ch_lock_table'],bytes(qualities))
        restore_fields=(('hd_banks',128*131),('ch_lock_table',8192),
                        ('ha_lanes',4736),('ch_lock_status',1))
        # Seeded roots already use canonical NOTE mirrors and detached
        # contexts, exactly as the persisted representation reconstructs.
        expected_restore=[1,bytes(roots).hex(),bytes(qualities).hex(),
                          bytes(u.mem_read(s['ha_lanes'],4736)).hex(),
                          bytes(u.mem_read(s['ch_lock_status'],1)).hex()]
        def retain():
            m.call('ch_nv_save',0)
            return retained.snapshot(m).hex()
        yield f'harmony/retain_{name}',retain
        # Host-only setup is outside the measured callback. A successful
        # no-op restore must fail even if both images share the same bug.
        for label,size in restore_fields:
            u.mem_write(s[label],b'\xcc'*size)
        def restore():
            result=[m.call('ch_nv_restore',0),
                    *(bytes(u.mem_read(s[label],size)).hex() for label,size in restore_fields)]
            assert result==expected_restore,('restore did not reconstruct the saved bank',name)
            return result
        yield f'harmony/restore_{name}',restore



def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--artifacts',type=Path,default=ROOT/'out')
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--compare',type=Path)
    ap.add_argument('--repeat',type=int,default=2)
    a=ap.parse_args(); assert a.repeat>0
    fixture_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    previous_report=json.loads(a.compare.read_text()) if a.compare else None
    if previous_report is not None:
        assert previous_report.get('fixture_sha256')==fixture_sha256, (
            'benchmark fixture changed; rerun the baseline with this script',
            previous_report.get('fixture_sha256'),fixture_sha256)
    samples={}
    for repeat in range(a.repeat):
        m=CpuMachine(a.artifacts)
        for name,run in cases(m):
            record=m.profile(run); samples.setdefault(name,[]).append(record)
            if repeat==0:print(f'{name:43} {record[0]:>10,} instructions  {record[1]:>7,} max masked',flush=True)
    report={'measurement':'executed ColdFire instructions; not cycles or hardware timing',
            'image_sha256':hashlib.sha256((a.artifacts/'mainos_bus.bin').read_bytes()).hexdigest(),
            'fixture_sha256':fixture_sha256,
            'repeat':a.repeat,'cases':{}}
    previous=previous_report['cases'] if previous_report is not None else None
    for name,rows in samples.items():
        assert len({(n,p,h) for n,p,h,_ in rows})==1,('nondeterministic fixture',name,rows)
        n,peak,digest,hot=rows[0]
        value={'instructions':n,'max_masked':peak,'result_sha256':digest,'hotspots':hot}
        if previous:
            assert previous[name]['result_sha256']==digest,('behavior changed',name)
            value['baseline_instructions']=previous[name]['instructions']
            value['ratio']=n/previous[name]['instructions']
        report['cases'][name]=value
    if previous: assert set(previous)==set(samples),'benchmark case set changed'
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(f'Wrote {a.output}',flush=True)


if __name__=='__main__':main()
