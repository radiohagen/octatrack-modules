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
                               UC_M68K_REG_PC, UC_M68K_REG_SR, UC_M68K_REG_D0, UC_M68K_REG_D1,
                               UC_M68K_REG_D2, UC_M68K_REG_A0, UC_M68K_REG_A1)
ROOT = Path(__file__).resolve().parents[2]
CASES = ((21426141,0,0,0,0), (21426141,127,127,0,0),
         (21426141,96,110,40,30), (1024,127,127,127,127),
         (0xffffffff,127,127,127,127), (42726141,65,100,127,90))
COUNTS = (0, 1, 3, 16, 32, 65)
PHASES = (0xfffffff0,0x12345678,0x87654321,0x7fffffff,0x80000000,0xabcdef01,0x3210fedc,0x11223344)



def verify_adapter(uc, call, sym):
    """Check native stereo output, AMP ramp, counters and buffer bounds."""
    levels = ((0,0),(32768,32768),(12345,12345),(0,32768),
              (32768,0),(12345,23456),(65535,0),(40000,40000))
    counts = (0,1,3,16,32)
    source = '#include <stdio.h>\n#define SS_HOST_TEST\n#include "modules/supersaw/adapter.c"\nint main(void) {\n'
    source += 'uint32_t state[32]; int32_t out[64]; uint16_t fp[6]={16384,24576,28160,16384,10240,7680};\n'
    for previous,target in levels:
        for n in counts:
            source += 'ss_init(&ss_voices[0]);ss_active[0]=1;ss_samples[0]=0;\n'
            for _ in range(2):
                source += 'for(unsigned i=0;i<32;++i)state[i]=0;state[3]=21426141;'
                source += f'state[6]={target};*(uint16_t *)((uint8_t *)state+38)={previous};'
                source += f'ss_fill(0,(uint8_t *)state,fp,out,{n});fwrite(out,4,{2*n},stdout);'
                source += '{uint32_t tail[2]={*(uint16_t *)((uint8_t *)state+38),ss_samples[0]};fwrite(tail,4,2,stdout);}'
    source += 'return 0;}\n'
    with tempfile.TemporaryDirectory() as tmp:
        c,exe=Path(tmp)/'adapter.c',Path(tmp)/'adapter'
        c.write_text(source)
        subprocess.run(['cc','-O2','-fsanitize=address,undefined','-I',str(ROOT),str(c),'-o',str(exe)],check=True)
        raw=subprocess.check_output([str(exe)])
        expected=struct.unpack(f'={len(raw)//4}I',raw)
    actual=[]; costs=[]
    for previous,target in levels:
        for n in counts:
            call('ss_init',sym['ss_voices'])
            uc.mem_write(sym['ss_active'],b'\x01'+bytes(7))
            uc.mem_write(sym['ss_samples'],bytes(32))
            iterations=[]
            for _ in range(2):
                state=bytearray(128)
                struct.pack_into('>I',state,12,21426141)
                struct.pack_into('>I',state,24,target)
                struct.pack_into('>H',state,38,previous)
                uc.mem_write(0x24000,bytes(state))
                uc.mem_write(0x25000,struct.pack('>6H',16384,24576,28160,16384,10240,7680))
                uc.mem_write(0x26000,bytes([0xa5])*272)
                iterations.append(call('ss_fill',0,0x24000,0x25000,0x26000,n))
                actual.extend(struct.unpack(f'>{2*n}I',bytes(uc.mem_read(0x26000,n*8))))
                actual.append(int.from_bytes(uc.mem_read(0x24000+38,2),'big'))
                actual.append(int.from_bytes(uc.mem_read(sym['ss_samples'],4),'big'))
                assert bytes(uc.mem_read(0x26000+n*8,272-n*8))==bytes([0xa5])*(272-n*8), 'output overrun'
            if n==16:
                limit=1000 if previous==target else 1150
                assert iterations[1]<=limit, ('adapter instruction regression',previous,target,iterations,limit)
            costs.append(dict(previous=previous,target=target,samples=n,cold_instructions=iterations[0],warm_instructions=iterations[1]))
    assert tuple(actual)==expected, 'adapter output or envelope differs from host'
    return dict(exact_output_values=2*sum(counts)*len(levels)*2,costs=costs)


def verify_poly(uc,call,sym):
    """Cross-architecture native four-note adapter, including short calls."""
    source='#include <stdio.h>\n#define SS_HOST_TEST\n#include "modules/supersaw/adapter.c"\nint main(void){\n'
    source+='uint32_t state[32]={0},pool[4][16]={{0}};int32_t out[64];uint16_t fp[6]={16384,24576,28160,16384,10240,7680};ss_active[2]=1;((uint8_t *)state)[80]=1;\n'
    cases=[(n,g) for n in (0,1,3,16,32) for g in (16384,0,23170)]
    for n,g in cases:
        source+='for(unsigned v=0;v<4;++v){pool[v][3]=21426141*(v+1);pool[v][6]='+str(g)+';((uint8_t *)pool[v])[36]=1;}\n'
        source+=f'ss_track_fill(2,(uint8_t *)state,fp,out,{n},(uint8_t *)pool);fwrite(out,4,{2*n},stdout);\n'
        source+='for(unsigned v=0;v<4;++v){uint32_t x=*(uint16_t *)((uint8_t *)pool[v]+60);fwrite(&x,4,1,stdout); }\n'
    source+='}\n'
    with tempfile.TemporaryDirectory() as tmp:
        c,exe=Path(tmp)/'poly.c',Path(tmp)/'poly';c.write_text(source)
        subprocess.run(['cc','-O2','-fsanitize=address,undefined','-I',str(ROOT),str(c),'-o',str(exe)],check=True)
        raw=subprocess.check_output([str(exe)]);expected=struct.unpack(f'={len(raw)//4}I',raw)
    state=bytearray(128);state[80]=1;uc.mem_write(0x24000,bytes(state))
    uc.mem_write(0x25000,struct.pack('>6H',16384,24576,28160,16384,10240,7680))
    uc.mem_write(0x27000,bytes(256));uc.mem_write(sym['ss_active'],bytes([0,0,1,0,0,0,0,0]))
    actual=[];costs=[]
    for n,g in cases:
        for v in range(4):
            addr=0x27000+64*v
            uc.mem_write(addr+12,struct.pack('>I',21426141*(v+1)))
            uc.mem_write(addr+24,struct.pack('>I',g));uc.mem_write(addr+36,b'\x01')
        uc.mem_write(0x26000,bytes([0xa5])*272)
        count=call('ss_track_fill',2,0x24000,0x25000,0x26000,n,0x27000)
        actual.extend(struct.unpack(f'>{2*n}I',bytes(uc.mem_read(0x26000,n*8))))
        actual.extend(int.from_bytes(uc.mem_read(0x27000+64*v+60,2),'big') for v in range(4))
        assert bytes(uc.mem_read(0x26000+n*8,272-n*8))==bytes([0xa5])*(272-n*8)
        if n==16: assert count<5000, ('four-note adapter instruction budget',count)
        costs.append(dict(samples=n,target_gain=g,instructions=count))
    assert tuple(actual)==expected,'four-note native output differs from host'
    steady=call('ss_track_fill',2,0x24000,0x25000,0x26000,16,0x27000)
    assert steady<3800, ('four-note steady instruction budget',steady)
    uc.mem_write(sym['ss_setup']+12,bytes((64,64,80,64,1,83)))
    for _ in range(10): enabled=call('ss_track_fill',2,0x24000,0x25000,0x26000,16,0x27000)
    assert enabled<9400, ('four-note filtered steady instruction budget',enabled)
    uc.mem_write(sym['ss_setup']+12,bytes(6))
    return dict(exact_values=len(actual),costs=costs,steady_16_instructions=steady,filtered_steady_16_instructions=enabled)


def verify_filter(uc,call,sym):
    source='#include <stdio.h>\n#define SS_HOST_TEST\n#include "modules/supersaw/adapter.c"\nint main(void){struct ss_filter f={0};int16_t a[16];\n'
    cases=[(typ,cut,res,env,dec) for typ in (0,1,2,3,0) for cut,res,env,dec in ((16,0,0,0),(64,64,80,64),(127,127,127,127))]
    for j,(typ,cut,res,env,dec) in enumerate(cases):
        source+='for(unsigned k=0;k<20;++k){for(unsigned i=0;i<16;++i)a[i]=(int16_t)(i*1793+k*313);'
        source+=f'struct ss_filter_params p={{{cut},{res},{env},{dec},{typ}}};ss_filter_half(&f,&p,{j//3+1},a,16);fwrite(a,2,16,stdout);}}\n'
    source+='}\n'
    with tempfile.TemporaryDirectory() as tmp:
        c,e=Path(tmp)/'filter.c',Path(tmp)/'filter';c.write_text(source)
        subprocess.run(['cc','-O2','-fsanitize=address,undefined','-I',str(ROOT),str(c),'-o',str(e)],check=True)
        raw=subprocess.check_output([str(e)]);expected=struct.unpack(f'={len(raw)//2}h',raw)
    uc.mem_write(0x28000,bytes(36));actual=[];costs=[]
    for j,(typ,cut,res,env,dec) in enumerate(cases):
        uc.mem_write(0x28100,bytes((cut,res,env,dec,typ)))
        for k in range(20):
            a=[((i*1793+k*313+32768)%65536)-32768 for i in range(16)]
            uc.mem_write(0x28200,struct.pack('>16h',*a))
            n=call('ss_filter_half',0x28000,0x28100,j//3+1,0x28200,16)
            actual.extend(struct.unpack('>16h',bytes(uc.mem_read(0x28200,32))))
        costs.append(dict(type=typ,cutoff=cut,resonance=res,env=env,decay=dec,held_16_instructions=n))
    assert tuple(actual)==expected,'SEM host/ColdFire mismatch'
    return dict(exact_samples=len(actual),costs=costs)


def verify_migration(uc,call,sym):
    for address,size in ((0x42000000,0xa0000),(0x46c82000,4096),
                         (0x100a0000,0x20000),(0x100f8000,4096),(0x80000000,0x10000)):
        uc.mem_map(address,size)
    uc.mem_write(0x46c82456,struct.pack('>I',0x42000000))
    uc.mem_write(0x100b14cf,bytes((2,)))
    part=0x42000000+0x8ed80+6322*2
    track=3;row=0x1ec+30*track;fine=0x33+30*track
    uc.mem_write(part+fine,bytes((76,)))
    # Rendering a legacy track before its UI is opened must not migrate the
    # Part, saved shadow, live CUT or dirty flags. FINE still works immediately.
    regions=((part,6322),(0x100a4ece+6322*2,6322),(0x100f8598,4))
    before=[bytes(uc.mem_read(a,n)) for a,n in regions]
    uc.mem_write(0x800049d8+0xa8*track+8,struct.pack('>I',0x100b14f0))
    uc.mem_write(0x100b14f0,b'/AUDIO/FMSYNTH-SUPERSAW.wav\0')
    uc.mem_write(0x24000,bytes(128))
    call('ss_begin',track,0x24000)
    uc.mem_write(sym['ss_active']+track,b'\x01')
    call('ss_config',track)
    call('ss_fine',track,76<<8)
    assert uc.reg_read(UC_M68K_REG_D0)==76<<8
    assert [bytes(uc.mem_read(a,n)) for a,n in regions]==before, 'audio wrote persistent settings'
    assert bytes(uc.mem_read(sym['ss_setup']+6*track,6))==bytes((76,0,0,64,0,0))
    assert bytes(uc.mem_read(0x80000813+72*track,1))==b'\0'
    call('ss_prepare_setup',track)
    expected=bytes((76,0,0,64,0,83))
    assert bytes(uc.mem_read(part+row,6))==expected
    assert bytes(uc.mem_read(0x100a4ece+6322*2+row,6))==expected
    assert bytes(uc.mem_read(part+fine,1))==b'\x7f'
    assert bytes(uc.mem_read(0x80000813+72*track,1))==b'\x7f'
    # Once tagged, CUT remains CUT and FINE is never imported a second time.
    uc.mem_write(part+fine,bytes((31,)))
    call('ss_config',track)
    assert bytes(uc.mem_read(sym['ss_setup']+6*track,6))==expected
    assert bytes(uc.mem_read(part+fine,1))==bytes((31,))
    uc.mem_write(sym['ss_active']+track,b'\x01')
    call('ss_fine',track,31<<8)
    assert uc.reg_read(UC_M68K_REG_D0)==76<<8
    uc.mem_write(sym['ss_active']+track,b'\x00')
    call('ss_fine',track,31<<8)
    assert uc.reg_read(UC_M68K_REG_D0)==31<<8
    # A shared descriptor is immutable after its first publication. Build from
    # a distinctive donor and use another marker track with another donor:
    # no donor fields or callback pointers may change on the second hand-out.
    uc.mem_write(part+0x22+track,b'\x01')
    uc.mem_write(part+0x2cb+5*track,b'\0')
    uc.mem_write(0x100b14f0,b'/AUDIO/FMSYNTH-SUPERSAW.wav\0')
    donor=bytes((i*7+11)&255 for i in range(402))
    uc.mem_write(0x29000,donor)
    call('ss_page',0x29000,track)
    page=bytes(uc.mem_read(sym['ss_descriptor'],402))
    uc.mem_write(0x29000,bytes([0xa5])*402)
    call('ss_page',0x29000,track)
    assert bytes(uc.mem_read(sym['ss_descriptor'],402))==page
    assert uc.reg_read(UC_M68K_REG_D0)==sym['ss_descriptor']
    uc.mem_write(0x29000,donor)
    call('ss_lfo_page',0x29000,track)
    page=bytes(uc.mem_read(sym['ss_lfo_descriptor'],402))
    uc.mem_write(0x29000,bytes([0xa5])*402)
    call('ss_lfo_page',0x29000,track)
    assert bytes(uc.mem_read(sym['ss_lfo_descriptor'],402))==page
    # Non-Supersaw pages still return the caller's original descriptor.
    call('ss_page',0x29000,7)
    assert uc.reg_read(UC_M68K_REG_D0)==0x29000
    return dict(legacy_fine_preserved=True,default_off=True,one_time_migration=True,
                native_fine_fallback=True,audio_no_persistent_writes=True,immutable_descriptors=True)


def verify_native_ui(uc,call,sym):
    """Execute the composed image's real resolver and LFO name formatter.

    Open SETUP first, then SRC, alternate two marker tracks and stock FLEX,
    and prove all six LFO names through the installed hook, not a mock.
    """
    image=(ROOT/'out/mainos_bus.bin').read_bytes()
    mapped=list(uc.mem_regions())
    for address in range(0x40000000,(0x40000400+len(image)+4095)&~4095,4096):
        if not any(lo<=address<=hi for lo,hi,_ in mapped):uc.mem_map(address,4096)
    uc.mem_write(0x40000400,image)
    for name in ('ss_page_built','ss_lfo_built','po_pg_built','po_lfo_built'):
        uc.mem_write(sym[name],b'\0')
    sym['stock_lfo_formatter']=0x4003bf64
    sym['stock_page_resolver']=0x40031da4
    part=0x42000000+0x8ed80+6322*2
    uc.mem_write(0x80000003,b'\x02')
    for t in (2,3,5):
        uc.mem_write(part+0x22+t,b'\x01')
        uc.mem_write(part+0x2cb+5*t,bytes((1 if t==5 else 0,)))
    uc.mem_write(0x100b14f0+0x448,b'/AUDIO/KICK.wav\0')
    call('ss_setup_page',0x400d31ae,3,1)
    assert uc.reg_read(UC_M68K_REG_D0)==sym['ss_descriptor'],'SETUP did not use canonical SRC'
    descriptor=bytes(uc.mem_read(sym['ss_descriptor'],402))
    assert descriptor[9:18]==b'SUPERSAW\0'
    assert int.from_bytes(descriptor[0x6a:0x6e],'big')==0,'inherited FLEX pitch minimum'
    assert int.from_bytes(descriptor[0x9a:0x9e],'big')==128,'inherited FLEX pitch count'
    assert int.from_bytes(descriptor[0x12a:0x12e],'big')==sym['po_knob']
    names=('PTCH','DETU','MORF','CUT','SUB','DRIV')
    for track in (3,2,5,3):
        uc.mem_write(0x80000000,bytes((track,)))
        wanted=('PTCH','STRT','LEN','RATE','RTRG','RTIM') if track==5 else names
        for slot,name in enumerate(wanted):
            uc.mem_write(0x29000,bytes([0xa5])*32)
            call('stock_lfo_formatter',0x29000,slot)
            actual=bytes(uc.mem_read(0x29000,32)).split(b'\0')[0].decode()
            assert actual==name,(track,slot,actual,name)
            assert bytes(uc.mem_read(0x29010,16))==bytes([0xa5])*16,'formatter overrun'
        call('stock_page_resolver',track,0)
        assert uc.reg_read(UC_M68K_REG_D0)==(0x400d31ae if track==5 else sym['ss_descriptor'])
        assert bytes(uc.mem_read(sym['ss_descriptor'],402))==descriptor,'published page mutated'
    return dict(setup_first=True,canonical_pitch_controls=True,native_lfo_label_cases=24,
                stock_flex_fallback=True,stable_across_tracks=True)


def verify_voic_dial(uc,call,sym):
    """Check the compiled seven-argument stock drawer ABI and text bounds."""
    drawer=0x400479b4
    uc.mem_map(drawer & ~4095,4096)
    uc.mem_write(drawer,bytes.fromhex('4e75'))  # observe the stock call, then RTS
    calls=[]
    def observe(u,*_):
        sp=u.reg_read(UC_M68K_REG_A7)
        calls.append(struct.unpack('>7I',bytes(u.mem_read(sp+4,28))))
    hook=uc.hook_add(UC_HOOK_CODE,observe,begin=drawer,end=drawer)
    cases=((0xffffffff,0xffffffff,'1'),(0,0,'1'),(1,0,'1'),(2,42,'2'),(3,84,'3'),(4,127,'4'),
           (32,0,'1'),(255,0,'1'))
    for raw,position,label in cases:
        for flags in (0,1,8,128):
            call('ss_voic_dial',93,3,2,raw,flags,0x12345678,0x26000)
            assert calls[-1]==(93,3,2,position,flags,sym['ss_voic_dial_fmt'],0x26000)
            uc.mem_write(0x28000,bytes([0xa5])*16)
            call('ss_voic_dial_fmt',0x28000,position)
            assert bytes(uc.mem_read(0x28000,16))==label.encode()+b'\0'+bytes([0xa5])*14
    uc.hook_del(hook)
    return dict(cases=len(calls),positions=[0,42,84,127],inherited_value_32_displays_one=True)


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
    for name,n in [('ss_page_built',1),('ss_lfo_built',1),('ss_active',8),('ss_samples',32),('ss_unsupported',32),('ss_voices',size),('ss_poly_voices',4*size),('ss_poly_samples',128),('ss_descriptor',402),('ss_lfo_descriptor',402),('ss_filters',1440),('ss_setup',48),('ss_note_stamp',32),('ss_filter_samples',32)]:
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
    # Signed detents and untouched stock SPD3 values use the native stack ABI.
    # The caller's final descriptor clamp is checked in the live panel gate.
    for value in (0,1,2,3,4,32,255):
        for delta in (-127,-1,0,1,127):
            call('ss_voic_knob',2,delta & 0xffffffff,value)
            expected=((value if 1<=value<=4 else 1)+delta)&0xffffffff
            assert uc.reg_read(UC_M68K_REG_D0)==expected,('VOIC step',value,delta)
    voic_dial=verify_voic_dial(uc,call,sym)
    source = '#include <stdio.h>\n#include "modules/supersaw/engine.c"\nint main(void) {\n'
    source += 'struct ss_voice v; int16_t out[65];\n'
    for case in CASES:
        for n in COUNTS:
            source += 'v=(struct ss_voice){{'+','.join(str(p)+'u' for p in PHASES[:2])+'},'+str(PHASES[2])+'u};\n'
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
            initial = struct.pack('>3I',*PHASES[:3])+bytes(stride-12)
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
                # S6 fixed pair plus sub and four-point interpolation.
                limit = 520 if case[1:] == (0,0,0,0) else 750
                assert warm <= limit, ('render instruction regression',case,warm,limit)
            costs.append(dict(params=case,samples=n,cold_instructions=cold,warm_instructions=warm))
    assert tuple(actual)==expected, [(i,a,b) for i,(a,b) in enumerate(zip(actual,expected)) if a!=b][:10]
    sem=verify_filter(uc,call,sym)
    adapter=verify_adapter(uc,call,sym)
    poly=verify_poly(uc,call,sym)
    # Exercise the actual assembly carry hook, not just the C copy helper.
    history=bytes((i*37+9)&255 for i in range(stride))
    uc.mem_write(sym['ss_voices']+2*stride,history)
    uc.mem_write(sym['ss_native_voices']+2*256+64+48,struct.pack('>I',123))
    filter_history=bytes(24)+struct.pack('>IIHBB',54321,456,128,1,1)
    uc.mem_write(sym['ss_filters']+(2*5+4)*36,filter_history)
    saved={UC_M68K_REG_D0:0x12345678,UC_M68K_REG_D1:0x87654321,
           UC_M68K_REG_A0:0x25000,UC_M68K_REG_A1:sym['ss_native_voices']+2*256+64}
    for reg,value in saved.items(): uc.reg_write(reg,value)
    uc.reg_write(UC_M68K_REG_D2,2)
    call('ss_carry_hook')
    assert bytes(uc.mem_read(sym['ss_poly_voices']+(2*4+1)*stride,stride))==history
    assert all(uc.reg_read(reg)==value for reg,value in saved.items()),'carry hook register corruption'
    assert bytes(uc.mem_read(sym['ss_filters']+(2*5+1)*36,36))==filter_history[:28]+struct.pack('>I',123)+filter_history[32:]
    poly['carry_hook_registers_and_history']=True
    migration=verify_migration(uc,call,sym)
    ui=verify_native_ui(uc,call,sym)
    (out/'receipt.json').write_text(json.dumps(dict(image_sha256=hashlib.sha256((ROOT/'out/mainos_bus.bin').read_bytes()).hexdigest(),
        exact_samples=len(actual),initialized_bytes=2+8+32+32+5*size+128+402+402+1440+48+32+32,costs=costs,adapter=adapter,poly=poly,filter=sem,migration=migration,ui=ui,voic_dial=voic_dial,hardware_tested=False),indent=2)+'\n')
    print(f'[ok] linked ColdFire: initialized state, {len(actual)} exact host samples, split-call sizes, native AMP/stereo adapter, instruction budgets, phase wrap and extreme pitches')

if __name__=='__main__': main()
