#!/usr/bin/env python3
"""Supersaw audio and real panel input under load, without borrowing main's idle task."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import toolpath
import blockdump
import recloop
from hw import ot_project as otp
from verify_supersaw_port import fixture, rms
sys.path.insert(0, str(ROOT/'tools/emu'))
import lcd_view


def analyze(work, tracks, control="DETU"):
    cmd = json.loads((work/'command.json').read_text())
    image = Path(cmd[cmd.index('--image')+1])
    project = Path(cmd[cmd.index('--card')+1]).parent/'project'
    log = (work/'port.log').read_text()
    assert 'ended on quit' in log and 'LOAD PROJECT handled' in log
    assert all(x not in log for x in ('WAIT TIMEOUT','ended early','unimplemented opcode','DID NOT RETURN'))
    knob, initial, change = (1,96,5) if control=="DETU" else (2,110,-20)
    lane = 0x80000810+72*tracks[0]+knob
    for value in (f"{initial+change:02x}",f"{initial:02x}"):
        assert f'wait {lane:#x} {value} eq met' in log, 'encoder update did not reach the live lane'
    n = int(re.search(r'over (\d+) frames, ended on quit',log)[1])
    rows = blockdump.read(work/'blocks.bin')
    end = max(row[1] for row in rows)
    rows = [row for row in rows if row[1] > end-n]
    spans = []
    for core in (0,1):
        frames = [r[1] for r in rows if r[0]=='<' and r[2]==1 and r[3]==core]
        # The live-script counter includes its initial frame 0, before the
        # first DSP block. Every subsequent frame must be present on both cores.
        assert frames and frames == list(range(min(frames),max(frames)+1))
        assert len(frames) >= n-1, ('missing DSP frames',core,len(frames),n)
        spans.append((frames[0],frames[-1],len(frames)))
    assert spans[0] == spans[1], ('asymmetric DSP output',spans)
    classes = blockdump.classes(rows)
    audio, comparison = {}, []
    for t in tracks:
        source = recloop.track_audio(classes,t+1)
        output = recloop.readback_audio(classes,t+1)
        assert len(source) == len(output) == spans[0][2]*16
        metrics = dict(source_rms=rms(source[44100:57330]),
            output_rms=rms(output[44100:57330]),
            source_tail_rms=rms(source[int(2.65*44100):int(2.85*44100)]),
            output_tail_rms=rms(output[int(2.65*44100):int(2.85*44100)]))
        assert metrics['source_rms'] > 100 and metrics['output_rms'] > 100, ('silent',t)
        assert metrics['source_tail_rms'] < 8 and metrics['output_tail_rms'] < 8, ('note-off',t)
        audio[f'T{t+1}'] = metrics
        if len(comparison) < 2: comparison.append(source)
    def delta(start,end):
        a,b=int(start*44100),int(end*44100)
        x,y=(v[a:b] for v in comparison)
        return rms([i-j for i,j in zip(x,y)])/rms(y)
    before,after=delta(1.,1.3),delta(1.7,2.1)
    assert before < 1e-6 and after > .01, ('encoder audio response',before,after)
    lanes = (work/'lanes.bin').read_bytes()
    assert list(lanes[72*tracks[0]:72*tracks[0]+6]) == [64,96,110,127,40,30]
    counts = struct.unpack('>8I',(work/'ss_samples.bin').read_bytes())
    assert all(n>60000 if t in tracks else n==0 for t,n in enumerate(counts)), counts
    assert (work/'ss_unsupported.bin').read_bytes() == bytes(32)
    records = (work/'dsp-records.bin').read_bytes()
    bank = (project/'bank01.work').read_bytes()
    for offset,field in ((otp.FX1_OFF,54),(otp.FX2_OFF,56)):
        expected = list(bank[otp.PART_BASE+offset:otp.PART_BASE+offset+8])
        actual = [int.from_bytes(records[t*64+field:t*64+field+2],'big') for t in range(8)]
        assert actual == expected, ('FX slot changed',actual,expected)
    plane = work/('lcd.bin' if (work/'lcd.bin').exists() else 'lcd.pbm')
    data = lcd_view.read_plane(plane)
    lcd_view.png(lcd_view.composite(lcd_view.pixels(data),data),work/'lcd.png')
    receipt = dict(result='pass',image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
        simultaneous_tracks=len(tracks),frames=spans[0][2],script_frame_counter=n,
        audio=audio,encoder_audio_response=dict(before_relative_difference=before,after_relative_difference=after),
        ss_samples=counts,control=control,real_panel=True,hardware_tested=False,command=cmd)
    (work/'audio-ui-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(f'[ok] {len(tracks)} Supersaw tracks: real panel {control} edit changes audio, note-off, continuous output on both cores, unchanged FX slots',flush=True)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--project',type=Path)
    mode.add_argument('--analyze',type=Path,help='inspect an existing capture without rerunning firmware')
    parser.add_argument('--tracks',default='1,2,3,4,5,6,7,8')
    parser.add_argument('--name',default='panel-eight')
    parser.add_argument('--control',choices=('DETU','MORF'),default='DETU')
    args = parser.parse_args()
    tracks = tuple(int(t)-1 for t in args.tracks.split(','))
    assert 2<=len(tracks)<=8 and len(set(tracks))==len(tracks) and all(0<=t<8 for t in tracks)
    if args.analyze:
        analyze(args.analyze,tracks,args.control)
        return
    work = ROOT/'out/supersaw-port'/args.name
    work.mkdir(parents=True,exist_ok=False)
    fixture(args.project,work,tracks,True)
    shutil.copy2(ROOT/'out/mainos_bus.bin',work/'candidate.bin')
    raw = subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True)
    sym = {f[2]:int(f[0],16) for line in raw.splitlines() if len(f:=line.split())==3}
    knob, initial, change = (1,96,5) if args.control=="DETU" else (2,110,-20)
    lane = 0x80000810+72*tracks[0]+knob
    rows=['0 key 0x32 down','40 key 0x32 up','100 pot 128',
        f'200 key {0x10+tracks[0]:#x} down',f'240 key {0x10+tracks[0]:#x} up',
        '400 key 0x22 down','440 key 0x22 up','660 key 0x28 down','700 key 0x28 up']
    rows += [f'800 midi {0x90+t:02x} 54 64' for t in tracks]
    rows += [f'1400 enc {knob} {change}',f'1900 wait {lane:#x} {initial+change:02x} eq 1']
    rows += [f'2300 midi {0x80+t:02x} 54 00' for t in tracks]
    rows += [f'2900 enc {knob} {-change}',f'3000 wait {lane:#x} {initial:02x} eq 1','3200 quit']
    (work/'panel.script').write_text('\n'.join(rows)+'\n')
    dumps=';'.join(f'{sym[k]:#x},32={work}/{k}.bin' for k in ('ss_samples','ss_unsupported'))
    dumps+=f';0x80000110,512={work}/dsp-records.bin;0x80000810,576={work}/lanes.bin'
    cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(work/'candidate.bin'),'--card',str(work/'card.img'),
        '--set','OCTABAM','--project','SYNTH','--mkii','--load-ms','90000','--dsp','--internal-clock',
        '--live-script',str(work/'panel.script'),'--lcd',str(work/'lcd.bin'),
        '--audio-out',str(work/'audio'),'--block-dump',str(work/'blocks.bin'),'--mem-dump',dumps]
    (work/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
    with (work/'port.log').open('w') as log:
        result=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=300)
    assert result.returncode == 0, work/'port.log'
    analyze(work,tracks,args.control)


if __name__=='__main__': main()
