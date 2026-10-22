#!/usr/bin/env python3
"""CPU source audio through the full firmware, with both stock FX slots free."""
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
import wave
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import toolpath
import ab_fixture
import blockdump
import emu_card
import recloop
import verify_repitch as sample
from hw import ot_project as otp
from remix import registry


def fixture(source, work, tracks, rich, sequence=False, fx=False, mixed=False, fx_pair=('FILTER','DELAY'), voices=1, chord=0, hold=127, filter_type=0):
    base = ab_fixture.prepare(source, work/'base')
    sample.SAMPLE_REL = 'AUDIO/FMSYNTH-SUPERSAW.wav'
    sample.LOOP_FRAMES = 4*44100
    sample.build_project(base, work/'project', 0, 2, 120, 64, 64)
    project = work/'project'
    for path in project.glob('project.*'):
        raw = path.read_bytes()
        for key, value in [('MIDI_AUDIO_TRK_NOTE_IN', 1), ('MIDI_AUDIO_TRK_CC_OUT', 0)]:
            raw = re.sub(key.encode()+rb'=\d+', f'{key}={value}'.encode(), raw)
        if mixed:
            raw = re.sub(rb'\[SAMPLE\]\r\nTYPE=FLEX\r\nSLOT=002\r\n.*?\[/SAMPLE\]\r\n\r\n', b'', raw, flags=re.S)
            first = re.search(rb'\[SAMPLE\]\r\nTYPE=FLEX\r\nSLOT=001\r\n.*?\[/SAMPLE\]\r\n\r\n', raw, re.S).group()
            raw = raw.replace(first, first+first.replace(b'SLOT=001', b'SLOT=002').replace(b'FMSYNTH-SUPERSAW.wav', b'FMSYNTH.wav'))
        path.write_bytes(raw)
    if mixed:
        for path in project.glob('markers.*'):
            raw = bytearray(path.read_bytes())
            raw[0x16+784:0x16+1568] = raw[0x16:0x16+784]
            raw[-2:] = (sum(raw[0x10:-2]) & 65535).to_bytes(2, 'big')
            path.write_bytes(raw)
    for path in project.glob('bank*.work'):
        def edit(data):
            for part in range(8):
                b = otp.PART_BASE+part*otp.PART_STRIDE+9
                for t in range(8):
                    data[b+0x22+t] = 1
                    data[b+0x2ca+5*t+1] = int(mixed and t == tracks[-1])
                    at = b+0x2a+30*t+6
                    params = (64,96,110,96 if filter_type else 127,40,30) if rich else (64,0,0,127,0,0)
                    if mixed and t == tracks[-1]:
                        params = (64,0,0,64,0,127)
                    data[at:at+6] = bytes(params)
                    if not (mixed and t == tracks[-1]):
                        setup=b+0x1da+18+30*t
                        data[setup:setup+6]=bytes((64,40,0,64,filter_type,83))
                    data[b+0x1da+30*t+6:b+0x1da+30*t+12] = bytes((1,0,0,0,0,0))
                    at = b+0x11a+24*t
                    data[at:at+6] = bytes((0,0,voices,0,0,chord))
                    data[at+6:at+12] = bytes((0,hold,10,64,64,127))
            for pattern in range(16):
                for t in range(8):
                    at = otp.trac_off(pattern,t)
                    data[at:at+64] = bytes(64)
                    if sequence and t in tracks:
                        data[at:at+8] = (1).to_bytes(8,'big')
                    at = 0x492e+pattern*0x8eec+t*0x8b9
                    data[at+9:at+33] = bytes(24)
        otp._bank_write(project,int(path.stem[4:]),edit,guard=False)
    if fx:
        for t in tracks:
            for slot,name in zip(('fx1','fx2'),fx_pair):
                values = otp.module_defaults(registry.modules()[name])
                if name == 'FILTER': values[:6] = [0,127,0,0,0,0]
                if name == 'DELAY': values[:6] = [64,0,0,0,0,0]
                otp.set_fx(project,slot,t+1,name,page=values[:6],page2=values[6:12],guard=False)
    marker = work/'FMSYNTH-SUPERSAW.wav'
    with wave.open(str(marker),'wb') as w:
        w.setparams((1,2,44100,0,'NONE','not compressed'))
        w.writeframes(bytes(4*44100*2))
    card,_ = emu_card.stage_project(project,'OCTABAM','SYNTH',tree=work/'tree',
        audio=[f'{marker}:AUDIO/{name}.wav' for name in ('FMSYNTH-SUPERSAW','FMSYNTH')])
    (work/'card.img').write_bytes(card)


def rms(values):
    return math.sqrt(sum(v*v for v in values)/max(1,len(values)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    mode=ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--project',type=Path)
    mode.add_argument('--analyze',type=Path,help='recheck a completed capture without rerunning firmware')
    ap.add_argument('--tracks',default='2,6')
    ap.add_argument('--rich',action='store_true')
    ap.add_argument('--sequence',action='store_true')
    ap.add_argument('--fx',action='store_true')
    ap.add_argument('--fx-pair',default='FILTER,DELAY')
    ap.add_argument('--mixed',action='store_true')
    ap.add_argument('--name',default='baseline')
    args = ap.parse_args()
    tracks = tuple(int(t)-1 for t in args.tracks.split(','))
    assert tracks and len(set(tracks)) == len(tracks) and all(0 <= t < 8 for t in tracks)
    if args.analyze:
        analyze(args.analyze,tracks,args.rich,args.sequence,args.mixed)
        return
    work = ROOT/'out/supersaw-port'/args.name
    work.mkdir(parents=True,exist_ok=True)
    assert not (work/'project').exists(), 'use a new case name to retain previous evidence'
    fixture(args.project,work,tracks,args.rich,args.sequence,args.fx,args.mixed,tuple(args.fx_pair.split(',')))
    frozen = ROOT/'out/supersaw-frozen'
    frozen.mkdir(exist_ok=True)
    for src,dst in [('out/mainos_bus.bin','candidate.bin'),('out/platform/runtime/runtime.elf','runtime.elf')]:
        shutil.copy2(ROOT/src,frozen/dst)
    shutil.copy2(frozen/'candidate.bin',work/'candidate.bin')
    raw = subprocess.check_output(['m68k-elf-nm',str(frozen/'runtime.elf')],text=True)
    sym = {f[2]:int(f[0],16) for line in raw.splitlines() if len(f:=line.split())==3}
    midi = work/'input.midi'
    rows = []
    if not args.sequence:
        for frame,on in [(100,True),(1400,False)]:
            for t in tracks:
                rows.append(f'{frame} {(0x90 if on else 0x80)+t:02x} 54 {"64" if on else "00"}')
    midi.write_text('\n'.join(rows)+'\n')
    cmd = [str(ROOT/'out/emu/ot_emu'),'--image',str(work/'candidate.bin'),
        '--card',str(work/'card.img'),'--set','OCTABAM','--project','SYNTH',
        '--mkii','--load-ms','90000','--sequencer','--internal-clock','--frames','3000',
        '--dsp','--main-level','64','--audio-out',str(work/'audio'),
        '--block-dump',str(work/'blocks.bin'),'--midi',str(midi),
        '--mem-dump',';'.join(f'{sym[k]:#x},32={work}/{k}.bin' for k in ['ss_samples','ss_unsupported'])+
            f';0x80000110,512={work}/dsp-records.bin']
    # This must return while voices are sounding: catches engine starvation.
    cmd += ['--step','500:call:0x40031da4,1,0']
    for t in tracks:
        cmd += ['--step',f'1800:call:0x40006820,{t}']
    (work/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
    with (work/'port.log').open('w') as log:
        result = subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=600)
    assert result.returncode == 0, work/'port.log'
    analyze(work,tracks,args.rich,args.sequence,args.mixed)


def analyze(work,tracks,rich=False,sequence=False,mixed=False):
    cmd=json.loads((work/'command.json').read_text())
    log = (work/'port.log').read_text()
    assert 'run ended REACHED' in log, work/'port.log'
    assert 'LOAD PROJECT handled' in log
    assert all(x not in log for x in ('DID NOT RETURN','main never spun','unimplemented opcode')), work/'port.log'
    blocks = blockdump.read(work/'blocks.bin')
    end = max(row[1] for row in blocks)
    blocks = [row for row in blocks if row[1] > end-3000]
    for core in (0,1):
        frames = [r[1] for r in blocks if r[0]=='<' and r[2]==1 and r[3]==core]
        assert frames == list(range(end-2999,end+1)), ('incomplete DSP frames',core)
    classes = blockdump.classes(blocks)
    metrics = {}
    for t in tracks:
        audio = recloop.readback_audio(classes,t+1)
        assert len(audio) == 48000
        sounding = audio[500*16:1100*16]
        level, quiet = rms(sounding), rms(audio[-400*16:])
        assert level > 100, ('silent',t,level)
        assert quiet < max(2,level*.001), ('did not stop',t,quiet)
        if not sequence:
            # Source release must be silent. FX output may still contain the
            # filter/delay tail; confusing the two rejects a correct note-off.
            source = recloop.track_audio(classes,t+1)
            assert len(source) == 48000
            assert rms(source[1650*16:1750*16]) < 8, ('source note-off',t)
        # The detuned pair/pulse can cross zero twice per fundamental cycle.
        # Find the strongest non-DC spectral peak over the entire spectrum,
        # without restricting the search to the expected pitch's octave.
        power=np.abs(np.fft.rfft(np.asarray(sounding)*np.hanning(len(sounding)),n=4*len(sounding)))
        freqs=np.fft.rfftfreq(4*len(sounding),1/44100)
        power[freqs<20]=0
        hz=float(freqs[np.argmax(power)])
        if not rich:
            assert abs(hz-261.6256) < 2, ('C4 pitch',t,hz)
        metrics[f'T{t+1}'] = dict(rms=level,stopped_rms=quiet,spectral_peak_hz=hz)
    counts = struct.unpack('>8I',(work/'ss_samples.bin').read_bytes())
    ss_tracks = set(tracks[:-1] if mixed else tracks)
    assert all(n>16000 if t in ss_tracks else n==0 for t,n in enumerate(counts)), counts
    assert (work/'ss_unsupported.bin').read_bytes() == bytes(32)
    records = (work/'dsp-records.bin').read_bytes()
    bank = (work/'project/bank01.work').read_bytes()
    for offset,field in [(otp.FX1_OFF,54),(otp.FX2_OFF,56)]:
        expected = list(bank[otp.PART_BASE+offset:otp.PART_BASE+offset+8])
        actual = [int.from_bytes(records[t*64+field:t*64+field+2],'big') for t in range(8)]
        assert actual == expected, ('FX routing',field,actual,expected)
    cpu = re.search(r'cpu\s+: (.*)',log)
    receipt = dict(image_sha256=hashlib.sha256((work/'candidate.bin').read_bytes()).hexdigest(),
        audio=metrics,ss_samples=counts,cpu=cpu.group(1) if cpu else None,
        hardware_tested=False,command=cmd)
    (work/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('[ok]',work.name,metrics,receipt['cpu'],flush=True)


if __name__ == '__main__':
    main()
