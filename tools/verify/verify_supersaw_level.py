#!/usr/bin/env python3
"""Native MIDI level at VOIC 1..4 and real four-position filter selector.

--baseline verifies the old -3/-4.8/-6 dB failure using a frozen S7 image,
so an unchanged implementation cannot accidentally pass the new level gate.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/verify')]
import toolpath,emu_card,blockdump,recloop,lcd_view,slots
from hw import ot_project as otp
from verify_supersaw_port import fixture,rms


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project',type=Path,required=True)
    ap.add_argument('--name',required=True)
    ap.add_argument('--baseline',type=Path)
    a=ap.parse_args();w=ROOT/'out/supersaw-port'/a.name;w.mkdir(parents=True,exist_ok=False)
    fixture(a.project,w,(0,1,2,3),False,voices=4)
    for path in (w/'project').glob('bank*.work'):
        def edit(d):
            for part in range(8):
                b=otp.PART_BASE+part*otp.PART_STRIDE+9
                for t in range(4):d[b+0x11a+24*t+2]=t+1
        otp._bank_write(w/'project',int(path.stem[4:]),edit,guard=False)
    card,_=emu_card.stage_project(w/'project','OCTABAM','SYNTH',tree=w/'level-tree',
        audio=[f'{w}/FMSYNTH-SUPERSAW.wav:AUDIO/FMSYNTH-SUPERSAW.wav'])
    (w/'card.img').write_bytes(card)
    runtime=a.baseline or ROOT/'out/platform/runtime'
    image=(a.baseline/'mainos_bus.bin') if a.baseline else ROOT/'out/mainos_bus.bin'
    shutil.copy2(image,w/'candidate.bin')
    raw=subprocess.check_output(['m68k-elf-nm',str(runtime/'runtime.elf')],text=True)
    sym={f[2]:int(f[0],16) for line in raw.splitlines() if len(f:=line.split())==3}
    rows=['0 key 0x32 down','40 key 0x32 up','100 pot 128','200 key 0x10 down',
          '240 key 0x10 up','400 key 0x22 down','440 key 0x22 up']
    for t in range(4):
        rows += [f'{800+5*t} midi {0x90+t:02x} 54 64',f'{1800+5*t} midi {0x80+t:02x} 54 00']
        for i,note in enumerate((84,88,91,95)[:t+1]):
            rows += [f'{2200+25*t+5*i} midi {0x90+t:02x} {note:02x} 64',
                     f'{3400+25*t+5*i} midi {0x80+t:02x} {note:02x} 00']
    if not a.baseline:
        rows += ['4000 key 0x2d down','4040 key 0x22 down','4080 key 0x22 up','4120 key 0x2d up',
                 '4400 enc 4 127','4600 key 0x3c down','4700 enc 4 7','4900 enc 4 1',
                 '5100 enc 4 1','5300 key 0x3c up','5500 enc 4 -1','5700 enc 4 -1',
                 '5900 enc 4 -1','6100 enc 4 -1','6300 enc 4 1']
        for ms,typ in ((4300,0),(4500,1),(4800,2),(5000,3),(5200,3),(5600,2),(5800,1),(6000,0),(6200,0),(6400,1)):
            rows.append(f'{ms} wait {sym["ss_setup"]+4:#x} {typ:02x} eq 1')
    rows.append('6600 quit');rows.sort(key=lambda r:int(r.split()[0]))
    (w/'panel.script').write_text('\n'.join(rows)+'\n')
    dumps=';'.join(f'{sym[k]:#x},{size}={w}/{k}.bin' for k,size in
        [('ss_native_voices',2048),('ss_descriptor',402),('ss_setup',48),('ss_unsupported',32)])
    dumps+=f';0x80000110,512={w}/dsp-records.bin'
    cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(w/'candidate.bin'),'--card',str(w/'card.img'),
         '--set','OCTABAM','--project','SYNTH','--mkii','--load-ms','90000','--dsp','--internal-clock',
         '--live-script',str(w/'panel.script'),'--audio-out',str(w/'audio'),'--block-dump',str(w/'blocks.bin'),
         '--lcd',str(w/'lcd.bin'),'--mem-dump',dumps]
    (w/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
    with slots.slot('Supersaw level and selector',root=ROOT) as env:
        with (w/'port.log').open('w') as log:
            result=subprocess.run(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
    assert result.returncode==0
    analyze(w,bool(a.baseline))


def analyze(w,baseline=False):
    log=(w/'port.log').read_text();assert 'ended on quit' in log and 'LOAD PROJECT handled' in log
    assert all(x not in log for x in ('WAIT TIMEOUT','DID NOT RETURN','unimplemented opcode'))
    n=int(re.search(r'over (\d+) frames, ended on quit',log)[1])
    blocks=blockdump.read(w/'blocks.bin');end=max(r[1] for r in blocks)
    blocks=[r for r in blocks if r[1]>end-n]
    for core in (0,1):
        assert [r[1] for r in blocks if r[0]=='<' and r[2]==1 and r[3]==core]==list(range(1,n))
    classes=blockdump.classes(blocks);levels=[];chords=[]
    for t in range(4):
        source=[x/256 for x in recloop.track_audio(classes,t+1)]
        levels.append(rms(source[int(1.1*44100):int(1.7*44100)]))
        chord=source[int(2.65*44100):int(3.25*44100)]
        chords.append(dict(rms=rms(chord),peak=max(map(abs,chord)),
                           clipped=sum(abs(x)>=32767 for x in chord)))
        assert rms(source[int(3.9*44100):int(4.0*44100)])<8,'stuck release'
    differences=[20*math.log10(x/levels[0]) for x in levels]
    expected=[0,-3.0103,-4.7712,-6.0206] if baseline else [0]*4
    assert all(abs(x-y)<.12 for x,y in zip(differences,expected)),(differences,expected)
    assert all(c['rms']>100 and c['clipped']==0 for c in chords),chords
    pool=(w/'ss_native_voices.bin').read_bytes();assert all(pool[t*256+v*64+36]==0 for t in range(4) for v in range(4))
    assert (w/'ss_unsupported.bin').read_bytes()==bytes(32)
    records=(w/'dsp-records.bin').read_bytes();bank=(w/'project/bank01.work').read_bytes()
    for off,field in ((otp.FX1_OFF,54),(otp.FX2_OFF,56)):
        assert [int.from_bytes(records[t*64+field:t*64+field+2],'big') for t in range(8)]==list(bank[otp.PART_BASE+off:otp.PART_BASE+off+8])
    if not baseline:
        descriptor=(w/'ss_descriptor.bin').read_bytes()
        assert struct.unpack_from('>I',descriptor,0xfa+40)[0]==0x40046c28
        assert struct.unpack_from('>I',descriptor,0x9a+40)[0]==4
        assert (w/'ss_setup.bin').read_bytes()[4]==1
    plane=lcd_view.read_plane(w/'lcd.bin');lcd_view.png(lcd_view.composite(lcd_view.pixels(plane),plane),w/'lcd.png')
    receipt=dict(result='pass',baseline=bool(baseline),image_sha256=hashlib.sha256((w/'candidate.bin').read_bytes()).hexdigest(),
                 single_note_rms=levels,relative_db=differences,chords=chords,selector=not bool(baseline),
                 fx_unchanged=True,no_stuck_notes=True,hardware_tested=False)
    (w/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('[ok] native VOIC 1..4 relative dB:',differences,'four-position selector:',not bool(baseline))


if __name__=='__main__':main()
