#!/usr/bin/env python3
"""Profile actual linked ColdFire render paths, not host timings.

Reports executed instructions and multiply/divide counts. These are not
hardware cycles: caches, bus contention and the surrounding OS are excluded.
Pass --runtime to retain a reproducible baseline across rebuilds.
Requires the repository's corrected Unicorn; the EMAC self-test fails closed.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import toolpath
from emu_bringup import emac_selftest
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.m68k_const import (UC_CPU_M68K_CFV4E, UC_M68K_REG_A7, UC_M68K_REG_PC,
                               UC_M68K_REG_SR, UC_M68K_REG_A4, UC_M68K_REG_A5,
                               UC_M68K_REG_D0, UC_M68K_REG_D2)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runtime', type=Path, default=ROOT/'out/platform/runtime')
    ap.add_argument('--output', type=Path, default=ROOT/'out/supersaw-cpu.json')
    ap.add_argument('--baseline',action='store_true',help='Measure an older runtime without enforcing new optimization budgets')
    args = ap.parse_args()
    emac_ok,emac_detail=emac_selftest()
    assert emac_ok,emac_detail
    elf = args.runtime/'runtime.elf'
    symbols = subprocess.check_output(['m68k-elf-nm', '-S', str(elf)], text=True)
    sym = {f[-1]: int(f[0], 16) for line in symbols.splitlines()
           if len(f := line.split()) in (3, 4)}
    sizes = {f[-1]: int(f[1], 16) for line in symbols.splitlines()
             if len(f := line.split()) == 4}
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
    if 'ss_diag_events' in sym:
        uc.mem_map(0xfc07c000,4096) # flat timer: instruction/stack counts only
    counts = Counter(); functions = Counter(); lowest=[0x20000]
    def tick(_uc, address, _size, _user):
        counts[op.get(address, 'unknown')] += 1
        lowest[0]=min(lowest[0],_uc.reg_read(UC_M68K_REG_A7))
        functions[owner.get(address, 'unknown')] += 1
    uc.hook_add(UC_HOOK_CODE, tick)
    def call(name, *values):
        counts.clear(); functions.clear(); lowest[0]=0x20000
        uc.reg_write(UC_M68K_REG_A7, 0x20000)
        uc.mem_write(0x20000, struct.pack('>'+'I'*(1+len(values)), 0x10000, *values))
        uc.emu_start(sym[name], 0x10000, count=100000)
        assert uc.reg_read(UC_M68K_REG_PC) == 0x10000, name
        assert uc.reg_read(UC_M68K_REG_A7) == 0x20004, 'stack imbalance'
        return dict(stack_bytes=0x20000-lowest[0],instructions=sum(counts.values()),
                    multiplies=sum(n for k,n in counts.items() if k.startswith('mul')),
                    emac_operations=sum(n for k,n in counts.items() if k.startswith(('mac','msac','maaac','masac','msaac','mssac'))),
                    # binutils prints ColdFire long division as remsl when
                    # quotient/remainder register fields coincide.
                    divides=sum(n for k,n in counts.items() if k.startswith(('div','rem'))),
                    functions=dict(functions))
    cases = []
    for voices in (0, 1, 2, 3, 4):  # 0 = native mono path, 1 = one poly voice
        for typ in (0, 1, 2, 3):
            for setting, sub, drive, amount in (('plain',0,0,0), ('rich',96,80,80),
                                               ('sub_only',96,0,0), ('drive_only',0,80,0)):
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
                # First-ever attack has no prepared oscillator coefficients;
                # distinguish it from a cold-phase retrigger on a warm cache.
                uc.mem_write(0x24000+24,struct.pack('>I',16384))
                uc.mem_write(0x24000+38,bytes(2))
                for v in range(voices):
                    uc.mem_write(0x27000+v*64+24,struct.pack('>I',16384))
                    uc.mem_write(0x27000+v*64+60,bytes(2))
                first_attack=call('ss_track_fill',0,0x24000,0x25000,0x26000,16,0x27000)
                uc.mem_write(base,data)
                uc.mem_write(sym['ss_active'],b'\x01'+bytes(7))
                uc.mem_write(sym['ss_setup'],bytes((64,64,amount,64,typ,83)))
                uc.mem_write(0x24000,bytes(state));uc.mem_write(0x27000,bytes(pool))
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
                                  cold=cold, warm=warm, first_attack=first_attack, cutoff_change=changed,pitch_change=pitch,**ramps))
    # Knob/envelope updates at the native 16-sample size must not reintroduce
    # coefficient/ramp divides. Pitch/AMP still have their own unrelated math.
    for case in cases:
        assert case['cutoff_change']['divides']==0, ('filter update divides',case)
    if not args.baseline:
        for case in cases:
            for phase in ('cold','first_attack','attack','release','pitch_change'):
                assert case[phase]['divides']==0, ('normal block divides',case,phase)
                # S11 native-frame maxima: mono 692 B, poly 536 B.
                limit=704 if case['voices']==0 else 544
                assert case[phase]['stack_bytes']<=limit, ('renderer stack regression',case,phase)
            if case['voices']:
                assert case['silent_tail']['instructions']<600, ('silent voice regression',case)
    # Native voices have actually retired, rather than merely having zero
    # gains while still active. Keep the output and counters well defined.
    uc.mem_write(base,data);uc.mem_write(sym['ss_active'],b'\x01')
    state=bytearray(128);state[80]=1
    uc.mem_write(0x24000,bytes(state));uc.mem_write(0x27000,bytes(256))
    uc.mem_write(0x26000,b'\xa5'*128)
    retired=call('ss_track_fill',0,0x24000,0x25000,0x26000,16,0x27000)
    assert bytes(uc.mem_read(0x26000,128))==bytes(128)
    assert int.from_bytes(uc.mem_read(sym['ss_samples'],4),'big')==16
    # Carry happens on the first mono-to-poly transition; its byte-copy
    # overhead is invisible when measuring only steady ss_track_fill calls.
    carry=[]
    voice_size=sizes['ss_voices']//8;filter_size=sizes['ss_filters']//40
    assert voice_size%4==filter_size%4==0
    for slot in range(4):
        uc.mem_write(base,data);uc.mem_write(sym['ss_active'],b'\x01')
        voice=bytes((i*19+slot*31)&255 for i in range(voice_size))
        filt=bytes((i*23+slot*41)&255 for i in range(filter_size))
        uc.mem_write(sym['ss_voices'],voice)
        uc.mem_write(sym['ss_filters']+4*filter_size,filt)
        pool_before=bytes(uc.mem_read(sym['ss_poly_voices'],sizes['ss_poly_voices']))
        filters_before=bytes(uc.mem_read(sym['ss_filters'],sizes['ss_filters']))
        stamp=0x12345678+slot
        cost=call('ss_carry',0,slot,stamp)
        expected_pool=bytearray(pool_before)
        expected_pool[slot*voice_size:(slot+1)*voice_size]=voice
        expected_filters=bytearray(filters_before)
        expected_filters[slot*filter_size:(slot+1)*filter_size]=filt
        struct.pack_into('>I',expected_filters,slot*filter_size+28,stamp)
        assert bytes(uc.mem_read(sym['ss_poly_voices'],len(expected_pool)))==expected_pool,('carry voice',slot)
        assert bytes(uc.mem_read(sym['ss_filters'],len(expected_filters)))==expected_filters,('carry filter/stamp/guards',slot)
        assert bytes(uc.mem_read(sym['ss_voices'],voice_size))==voice,('carry source changed',slot)
        carry.append(dict(slot=slot,**cost))
    # Two independent four-note tracks, sustained modulation rather than a
    # single convenient block. The same harness can profile a frozen baseline.
    scenarios=[]
    for label,typ,env,sub,drive,neutral in (
            ('dry',0,0,96,80,False),('low_sweep',1,80,96,80,False),
            ('bp_sweep',2,80,96,80,False),('hp_sweep',3,80,96,80,False),
            ('neutral_low',1,0,0,0,True)):
        uc.mem_write(base,data)
        for track in (2,3):
            uc.mem_write(sym['ss_active']+track,b'\x01')
            uc.mem_write(sym['ss_setup']+track*6,bytes((64,0 if neutral else 64,env,64,typ,83)))
            state=bytearray(128);state[80]=1
            uc.mem_write(0x24000+track*256,bytes(state))
            pool=bytearray(256)
            for voice in range(4):
                struct.pack_into('>I',pool,voice*64+12,21426141*(voice+1)+track*1973)
                struct.pack_into('>I',pool,voice*64+24,24000)
                struct.pack_into('>I',pool,voice*64+48,voice+1)
                struct.pack_into('>H',pool,voice*64+60,24000);pool[voice*64+36]=1
            uc.mem_write(0x27000+track*256,bytes(pool))
        costs=[]
        for frame in range(272):
            total=0
            for track in (2,3):
                cut=127 if neutral else 24+(frame*7+track*13)%104
                uc.mem_write(0x25000,struct.pack('>6H',16384,96<<8,64<<8,cut<<8,sub<<8,drive<<8))
                total+=call('ss_track_fill',track,0x24000+track*256,0x25000,0x26000,16,0x27000+track*256)['instructions']
            if frame>=16:costs.append(total)
        scenarios.append(dict(scenario=label,tracks=[3,4],voices_per_track=4,blocks=len(costs),
                              mean_instructions=sum(costs)/len(costs),max_instructions=max(costs)))
    # Keep realistic sustained paths distinct from per-call synthetic probes.
    # Sparse pools and asynchronous gains prevent an optimization benefiting
    # only all-four-held or all-four-attacking voices from looking universal.
    mixed_scenarios=[]
    for label,typ,sub,drive,lanes in (
            ('mono_plus_triad_dry',0,96,80,((5,True,()),(6,False,(0,2,3)))),
            ('sparse_sub_only',0,96,0,((3,False,(1,3)),)),
            ('sparse_drive_only',0,0,80,((3,False,(1,3)),)),
            ('dual_low',1,96,80,((2,False,(0,1,2,3)),(3,False,(0,1,2,3)))),
            ('dual_bp',2,96,80,((2,False,(0,1,2,3)),(3,False,(0,1,2,3)))),
            ('dual_hp',3,96,80,((2,False,(0,1,2,3)),(3,False,(0,1,2,3))))):
        uc.mem_write(base,data)
        for track,mono,slots in lanes:
            uc.mem_write(sym['ss_active']+track,b'\x01')
            state=bytearray(128);state[80]=int(not mono)
            struct.pack_into('>I',state,12,21426141+track*1973)
            uc.mem_write(0x24000+track*256,bytes(state))
            pool=bytearray(256)
            for v in slots:
                pool[v*64+36]=1
                struct.pack_into('>I',pool,v*64+12,21426141*(v+1)+track*1973)
                struct.pack_into('>I',pool,v*64+48,v+1)
            uc.mem_write(0x27000+track*256,bytes(pool))
        phase_results=[]
        for phase in ('attack_hold','one_lsb_gain','zero_gain','mixed_envelopes',
                      'steady_filter','cutoff_ramp','neutral_open','filter_resume','retired'):
            costs=[];stacks=[];muls=[];emacs=[];divs=[];owners=Counter()
            for frame in range(32):
                total=0;stack=0;multiplies=0;emac_operations=0;divides=0
                for track,mono,slots in lanes:
                    target=32768 if mono else 32767
                    if phase=='one_lsb_gain':target=1
                    elif phase in ('zero_gain','retired'):target=0
                    uc.mem_write(0x24000+track*256+24,struct.pack('>I',target))
                    for v in slots:
                        gain=target
                        if phase=='mixed_envelopes':
                            gain=(20000,frame*700,max(0,20000-frame*1000),0)[v]
                        uc.mem_write(0x27000+track*256+v*64+24,struct.pack('>I',gain))
                        if phase=='retired':uc.mem_write(0x27000+track*256+v*64+36,b'\x00')
                    cut=24+(frame*7+track*13)%104 if phase=='cutoff_ramp' else 127 if phase=='neutral_open' else 64
                    res=0 if phase=='neutral_open' else 84
                    uc.mem_write(sym['ss_setup']+track*6,bytes((64,res,0,64,typ,83)))
                    uc.mem_write(0x25000,struct.pack('>6H',16384,96<<8,64<<8,cut<<8,sub<<8,drive<<8))
                    result=call('ss_track_fill',track,0x24000+track*256,0x25000,0x26000,16,0x27000+track*256)
                    total+=result['instructions'];stack=max(stack,result['stack_bytes'])
                    multiplies+=result['multiplies'];divides+=result['divides']
                    emac_operations+=result['emac_operations']
                    owners.update(result['functions'])
                costs.append(total);stacks.append(stack);muls.append(multiplies);emacs.append(emac_operations);divs.append(divides)
            assert max(divs)==0,('deterministic native divide',label,phase)
            phase_results.append(dict(phase=phase,frames=len(costs),first_instructions=costs[0],
                                      mean_instructions=sum(costs)/len(costs),max_instructions=max(costs),
                                      second_half_mean_instructions=sum(costs[16:])/16,
                                      max_stack_bytes=max(stacks),mean_multiplies=sum(muls)/len(muls),
                                      mean_emac_operations=sum(emacs)/len(emacs),
                                      max_divides=max(divs),function_instructions=dict(owners)))
        mixed_scenarios.append(dict(scenario=label,tracks=[t+1 for t,_,_ in lanes],
                                   native_mono=[mono for _,mono,_ in lanes],
                                   active_slots=[list(slots) for _,_,slots in lanes],phases=phase_results))
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
                   hardware_cycles=False, emac_selftest=emac_detail,
                   multiply_count_scope='multiplies counts scalar mul instructions; emac_operations counts MAC-family instructions separately',
                   retired_poly=retired, mono_to_poly_carry=carry, two_tracks=scenarios, cases=cases,
                   mixed_track_scenarios=mixed_scenarios, fine_control=fine, native_poly_parameters=native)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2)+'\n')
    for c in cases:
        if c['voices'] in (0,4):
            print(c['voices'],c['type'],c['setting'],c['warm']['instructions'],
                  'mul',c['warm']['multiplies'],'div',c['warm']['divides'])
    print('fine',fine['instructions'],'native parameters',native)


if __name__ == '__main__':
    main()
