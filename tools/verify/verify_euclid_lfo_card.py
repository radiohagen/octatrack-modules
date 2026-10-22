#!/usr/bin/env python3
"""Native card-load/save acceptance for Euclid LFO; isolated generated card.

The firmware mounts FAT and loads the project through its engine task. No file
I/O or STORE callback is mocked. SAVE PROJECT is driven through the real panel
dispatch. Power-up tests restore an unsaved SRAM snapshot, including missing
and damaged-record fallback. A parameter poke seeds the edit; this is not a
full editor or physical-device acceptance test.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from concurrent.futures import ThreadPoolExecutor

ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import toolpath  # noqa: E402,F401
import emu_card  # noqa: E402
from hw import ot_project as otp  # noqa: E402


def wave_offsets(base,stride,header=0,saved_gap=0):
    return [base+part*stride+(saved_gap if part>=4 else 0)+header+offset+lane
            for part in range(8) for track in range(8)
            for offset in (0x2f5+30*track,0x4eb+36*track) for lane in range(3)]


def check_native_waves(data,base,stride,header=0,saved_gap=0):
    for offset in wave_offsets(base,stride,header,saved_gap):
        assert data[offset]==19, ('native WAVE selection lost/clamped',hex(offset),data[offset])
    for offset,value in rate_values(base,stride,header,saved_gap):
        assert data[offset]==value, ('native RATE lost/clamped',hex(offset),data[offset],value)

def rate_values(base,stride,header=0,saved_gap=0):
    for part in range(8):
        start=base+part*stride+(saved_gap if part>=4 else 0)+header
        for midi in range(2):
            for track in range(8):
                for lane in range(3):
                    speed=64 if (part+track+lane)%2 else 96
                    yield start+(0x3e8+32*track if midi else 0x11a+24*track)+lane,speed
                    yield start+(0x500+36*track if midi else 0x30a+30*track)+lane,(part+lane)%4

def run(args,log):
    with log.open('w') as out:
        result=subprocess.run([str(x) for x in args],cwd=ROOT,stdout=out,stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'command failed ({result.returncode}): {log}\n{log.read_text()[-3000:]}')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project',required=True,type=pathlib.Path)
    a=ap.parse_args()
    if not (a.project/'project.work').is_file() or not (a.project/'bank01.work').is_file():
        ap.error('--project needs project.work and bank01.work')
    parent=ROOT/'out/euclid-lfo-card'; parent.mkdir(exist_ok=True)
    out=pathlib.Path(tempfile.mkdtemp(prefix='load-',dir=parent))
    print(f'Native card test: {out}',flush=True)
    project=out/'project'; project.mkdir()
    sources={}
    for source in sorted(a.project.glob('*.work')):
        if source.name.startswith('eulf'): continue
        shutil.copy2(source,project/source.name)
        sources[source.name]=hashlib.sha256(source.read_bytes()).hexdigest()
    # WAVE itself remains in native Part storage; verify the appended choice
    # survives native validation, SAVE PROJECT and a fresh load for every lane
    # in all four working/saved Parts. Modify only this generated fixture.
    def select_wave(data):
        for offset,value in rate_values(otp.PART_BASE,otp.PART_STRIDE,9): data[offset]=value
        for offset in wave_offsets(otp.PART_BASE,otp.PART_STRIDE,9): data[offset]=19
    otp._bank_write(project,1,select_wave,guard=False)
    expected=bytearray()
    for bank in range(16):
        payload=bytearray()
        for part in range(8):
            for lane in range(48):
                payload.extend((8,3,(bank+part+lane)%8,(part+lane)%8,
                                (bank+lane)%128,48,2,(part+lane)%3,64,(bank+part)%31))
        header=b'EULF'+struct.pack('>II',1,len(payload))
        data=header+struct.pack('>I',zlib.crc32(header+payload))+payload
        if bank==1: data=None                          # Legacy missing file.
        elif bank==2:                                 # Future version, valid CRC.
            header=b'EULF'+struct.pack('>II',2,len(payload))
            data=header+struct.pack('>I',zlib.crc32(header+payload))+payload
        elif bank==3: data=b''                         # Existing empty file.
        elif bank==4: data+=b'\x00'                    # Trailing byte, not padding.
        elif bank==5: data=data[:-1]                   # Truncated payload.
        elif bank==6: data=data[:-1]+bytes([data[-1]^1]) # Bad CRC.
        if data is not None: (project/f'eulf{bank+1:02d}.work').write_bytes(data)
        expected.extend(bytes(3840) if 1<=bank<=6 else payload)
    run(['make','bus','REMIX=euclid-lfo'],out/'build.log')
    image=out/'mainos.bin'; shutil.copy2(ROOT/'out/mainos_bus.bin',image)
    nm=subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True)
    symbols={s[2]:int(s[0],16) for line in nm.splitlines() if len(s:=line.split())==3}
    card=out/'input.img'
    run([ROOT/'.venv/bin/python3','tools/emu/ot_emu/stage_card.py',project,'EUCLID','LFO',
         '--tree',out/'tree','--out',card],out/'stage.log')
    run([ROOT/'out/emu/ot_emu','--image',image,'--card',card,'--set','EUCLID','--project','LFO',
         '--load-ms','90000','--sequencer','--internal-clock','--frames','1',
         '--step',f'-:dump:{symbols["eul_bank"]:#x},61440={out / "loaded.bin"};'
                  f'0x40170f60,50578={out / "native-loaded.bin"};'
                  f'{symbols["eul_refused"]:#x},16={out / "refused.bin"};'
                  f'{symbols["eul_io_errors"]:#x},4={out / "errors.bin"}'],out/'boot.log')
    actual=(out/'loaded.bin').read_bytes()
    if actual!=expected:
        first=next((i for i,(x,y) in enumerate(zip(actual,expected)) if x!=y),min(len(actual),len(expected)))
        raise AssertionError(f'native load mismatch at byte {first} (bank {first//3840+1}); {out}')
    assert (out/'refused.bin').read_bytes()==bytes([int(2<=b<=6) for b in range(16)])
    assert (out/'errors.bin').read_bytes()==bytes(4)
    check_native_waves((out/'native-loaded.bin').read_bytes(),0,0x18b2,saved_gap=2)
    print('PASS: native FAT load, all valid banks and malformed/missing cases',flush=True)
    # Follow the established native SAVE PROJECT gesture. No engine-task file
    # callback is invoked artificially from the UI task.
    script=[]; now=1500
    def send(command,gap):
        nonlocal now
        script.append(f'{now} {command}'); now+=gap
    def tap(key,gap):
        send(f'key {key:#x} down',40); send(f'key {key:#x} up',gap)
    tap(0x32,400)
    send('key 0x2d down',40); tap(0x30,150); send('key 0x2d up',1000)
    tap(0x21,700); tap(0x20,500); tap(0x31,1100); tap(0x31,9000)
    send('quit',0)
    (out/'save.script').write_text('\n'.join(script)+'\n')
    saved=out/'saved.img'
    common=[ROOT/'out/emu/ot_emu','--image',image,'--set','EUCLID','--project','LFO','--load-ms','90000']
    run(common+['--card',card,'--step',f'-:poke:{symbols["eul_bank"]+1:#x}=6',
                '--step',f'-:call:{symbols["eul_changed"]:#x},0,0',
                '--live-script',out/'save.script','--card-out',saved,
                '--mem-dump',f'{symbols["eul_io_errors"]:#x},4={out / "save-errors.bin"}'],out/'save.log')
    contents={name.lower():data for name,data in emu_card.extract_image(saved.read_bytes()).items()}
    wanted=bytearray(expected); wanted[1]=6
    payload=wanted[:3840]; header=b'EULF'+struct.pack('>II',1,3840)
    encoded=header+struct.pack('>I',zlib.crc32(header+payload))+payload
    for extension in ('work','strd'):
        key=next((k for k in contents if k.endswith(f'/eulf01.{extension}')),None)
        assert key and contents[key]==encoded, f'SAVE PROJECT did not persist exact eulf01.{extension}: {out}'
    for bank in range(2,7):
        filename=f'eulf{bank+1:02d}.work'
        key=next((k for k in contents if k.endswith('/'+filename)),None)
        assert key and contents[key]==(project/filename).read_bytes(), f'refused file overwritten: {filename}'
    assert (out/'save-errors.bin').read_bytes()==bytes(4)
    for extension in ('work','strd'):
        key=next(k for k in contents if k.endswith(f'/bank01.{extension}'))
        check_native_waves(contents[key],otp.PART_BASE,otp.PART_STRIDE,9)
    run(common+['--card',saved,'--sequencer','--internal-clock','--frames','1',
                '--step',f'-:dump:{symbols["eul_bank"]:#x},61440={out / "reloaded.bin"};'
                         f'0x40170f60,50578={out / "native-reloaded.bin"}'],out/'reload.log')
    assert (out/'reloaded.bin').read_bytes()==wanted, f'saved card did not reload identically: {out}'
    check_native_waves((out/'native-reloaded.bin').read_bytes(),0,0x18b2,saved_gap=2)
    print('PASS: native panel SAVE PROJECT writes work/stored copies, preserves refused files, and reloads exactly',flush=True)
    # Snapshot SRAM immediately after edits, then boot from that SRAM with
    # normal power-up loading (--no-post), not an injected LOAD PROJECT.
    cs1=out/'unsaved-cs1.bin'; unsaved_card=out/'unsaved.img'
    changes=f'{symbols["eul_bank"]+1:#x}=6;{symbols["eul_bank"]+24*10+8:#x}=127'
    run(common+['--card',card,'--step',f'-:poke:{changes}',
                '--step',f'-:call:{symbols["eul_changed"]:#x},0,0',
                '--step',f'-:dump:0x10000000,1048576={cs1}',
                '--sequencer','--internal-clock','--frames','1','--card-out',unsaved_card],out/'unsaved.log')
    never_saved={k.lower():v for k,v in emu_card.extract_image(unsaved_card.read_bytes()).items()}
    work_key=next(k for k in never_saved if k.endswith('/eulf01.work'))
    assert never_saved[work_key]==(project/'eulf01.work').read_bytes(), 'unsaved fixture unexpectedly reached disk'
    retained=bytearray(cs1.read_bytes()); nv=0xf8600
    assert retained[nv:nv+4]==b'EUN1', f'SRAM journal was not initialized: {out}'
    assert retained[nv+16+4+1]==6 and retained[nv+16+24*16+4+8]==127
    nocache=bytearray(retained); nocache[nv:nv+4]=bytes(4)
    (out/'nocache-cs1.bin').write_bytes(nocache)
    torn=bytearray(retained); torn[nv+16+4+1]^=1
    (out/'torn-cs1.bin').write_bytes(torn)
    (out/'power.script').write_text('1500 key 0x32 down\n1540 key 0x32 up\n2500 quit\n')
    retained_expected=bytearray(expected); retained_expected[1]=6; retained_expected[24*10+8]=127
    torn_expected=bytearray(retained_expected); torn_expected[:10]=expected[:10]
    cases=[('unsaved',cs1,retained_expected),('nocache',out/'nocache-cs1.bin',expected),
           ('torn',out/'torn-cs1.bin',torn_expected)]
    def power(case):
        tag,state,want=case; dump=out/f'power-{tag}.bin'
        run(common+['--card',unsaved_card,'--cs1-in',state,'--no-post',
                    '--live-script',out/'power.script','--mem-dump',
                    f'{symbols["eul_bank"]:#x},61440={dump}'],out/f'power-{tag}.log')
        got=dump.read_bytes()
        if got!=want:
            first=next((i for i,(x,y) in enumerate(zip(got,want)) if x!=y),min(len(got),len(want)))
            raise AssertionError(f'power {tag}: first mismatch {first}, bank {first//3840+1}: {out}')
    with ThreadPoolExecutor(3) as pool: list(pool.map(power,cases))
    print('PASS: native power-up retains unsaved audio/MIDI edits; missing cache and one damaged record fall back correctly',flush=True)
    # One refused file, then all three answers through STORE's actual panel
    # prompt and a normal SAVE PROJECT. No direct call to an answer callback.
    refused_project=out/'refusal-project'; refused_project.mkdir()
    for source in project.glob('*.work'):
        if not source.name.startswith('eulf'): shutil.copy2(source,refused_project/source.name)
    header=b'EULF'+struct.pack('>II',2,3840)
    bad_file=header+struct.pack('>I',zlib.crc32(header+bytes(3840)))+bytes(3840)
    (refused_project/'eulf01.work').write_bytes(bad_file)
    refused_card=out/'refusal.img'
    run([ROOT/'.venv/bin/python3','tools/emu/ot_emu/stage_card.py',refused_project,'EUCLID','LFO',
         '--tree',out/'refusal-tree','--out',refused_card],out/'refusal-stage.log')
    header=b'EULF'+struct.pack('>II',1,3840)
    empty_file=header+struct.pack('>I',zlib.crc32(header+bytes(3840)))+bytes(3840)
    def answer(choice):
        tag=('ignore','overwrite','backup')[choice]
        events=[]; tick=1500
        def send(command,gap=600):
            nonlocal tick
            events.append(f'{tick} {command}'); tick+=gap
        def tap(key,gap=600):
            send(f'key {key:#x} down',40); send(f'key {key:#x} up',gap)
        tap(0x32); send('enc 1 1',800)  # First turn opens the refusal list.
        if choice: send(f'enc 6 {choice}',700)
        tap(0x31,1000)
        send('key 0x2d down',40); tap(0x30,150); send('key 0x2d up',1000)
        tap(0x21,700); tap(0x20,500); tap(0x31,1100); tap(0x31,9000)
        send('quit',0)
        script=out/f'answer-{tag}.script'; script.write_text('\n'.join(events)+'\n')
        result=out/f'answer-{tag}.img'
        run(common+['--card',refused_card,'--live-script',script,'--card-out',result,
                    '--mem-dump',f'{symbols["eul_refused"]:#x},16={out / (tag+"-refused.bin")};'
                                 f'{symbols["eul_io_errors"]:#x},4={out / (tag+"-errors.bin")}'],
            out/f'answer-{tag}.log')
        files={k.lower():v for k,v in emu_card.extract_image(result.read_bytes()).items()}
        work=next(k for k in files if k.endswith('/eulf01.work'))
        assert files[work]==(bad_file if choice==0 else empty_file), (tag,'working file',out)
        backup=next((k for k in files if k.endswith('/eulf01.bak')),None)
        assert (files[backup]==bad_file if backup else False)==(choice==2), (tag,'backup file',out)
        assert (out/f'{tag}-refused.bin').read_bytes()==bytes([int(choice==0)]+[0]*15), (tag,'refusal state',out)
        assert (out/f'{tag}-errors.bin').read_bytes()==bytes(4), (tag,'I/O error',out)
    with ThreadPoolExecutor(3) as pool: list(pool.map(answer,range(3)))
    print('PASS: native IGNORE/OVERWRITE/BACKUP prompt answers and SAVE PROJECT preserve or replace exactly the refused file',flush=True)
    receipt={'scope':'native FAT/project load and panel SAVE PROJECT/reload; valid/missing/future/empty/long/short/CRC cases',
             'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),
             'source_project':str(a.project.resolve()),'source_hashes':sources,
             'retention':'native power-up with unsaved SRAM, missing-cache and damaged-record cases',
             'refusal_answers':['IGNORE preserves bytes','OVERWRITE creates valid v1','BACKUP preserves original before replacement'],
             'separate_checks':['panel Part and UI gate','make check']}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(f'PASS: native card checkpoint receipt: {out / "receipt.json"}',flush=True)

if __name__=='__main__': main()
