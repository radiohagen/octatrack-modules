#!/usr/bin/env python3
"""All 48 Euclid LFOs with eight looping FLEX voices under the native port.

Compare stock SQR and EUCLID on the same composed image and generated project,
including a native Part change. Counts are software-model evidence, not a
measurement of hardware cycles, maximum remix load or physical underruns.
"""
import argparse
import hashlib
import json
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
import zlib

ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import toolpath  # noqa: E402,F401
from hw import ot_project as otp  # noqa: E402
from hw import ot_bank  # noqa: E402
from harness import stress_project  # noqa: E402
from harness import blockdump, recloop  # noqa: E402
from verify_euclid_lfo_card import run  # noqa: E402


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project',type=pathlib.Path)
    ap.add_argument('--analyze',type=pathlib.Path,help='reanalyze an existing run with its captured input metadata')
    ap.add_argument('--frames',type=int,default=6000)
    a=ap.parse_args()
    if a.analyze:
        inputs=json.loads((a.analyze/'inputs.json').read_text())
        verify_run(a.analyze,inputs['frames'],inputs['symbols'],inputs['source_hashes'])
        return
    if a.project is None: ap.error('--project is required for a new run')
    if a.frames<1200: ap.error('--frames must cover the Part change at frame 1000')
    if not (a.project/'project.work').is_file() or not (a.project/'bank01.work').is_file():
        ap.error('--project needs project.work and bank01.work')
    parent=ROOT/'out/euclid-lfo-load'; parent.mkdir(exist_ok=True)
    out=pathlib.Path(tempfile.mkdtemp(prefix='load-',dir=parent))
    print(f'Native load test: {out}',flush=True)
    project=out/'project'; project.mkdir()
    sources={}
    for source in sorted(a.project.glob('*.work')):
        if source.name.startswith('eulf'): continue
        shutil.copy2(source,project/source.name)
        sources[source.name]=hashlib.sha256(source.read_bytes()).hexdigest()
    stress_project.set_project_text(project)
    stress_project.set_markers(project)
    stress_project.make_sample(project/stress_project.SAMPLE_REL)
    def populate(data):
        ot_bank.check_tags(data)
        for part in range(8):
            base=otp.PART_BASE+part*otp.PART_STRIDE
            for track in range(8):
                data[base+otp.MTYPE_OFF+track]=1
                data[base+otp.FX1_OFF+track]=data[base+otp.FX2_OFF+track]=0
                data[base+0x2d3+5*track+1]=0
                data[base+0x1b+2*track]=55
                data[base+0x1e3+30*track+6]=1  # FLEX loop.
                data[base+0x1e3+30*track+10]=0 # TSTR off.
                data[base+0x33+30*track+6]=64
                data[base+0x33+30*track+9]=127
                for midi in (False,True):
                    p1=base+(0x3e8+9+32*track if midi else otp.LFO_P1_OFF+24*track)
                    p2=base+(0x4e8+9+36*track if midi else otp.LFO_PM_OFF+30*track)
                    timing=base+(0x500+9+36*track if midi else 0x30a+9+30*track)
                    data[p1:p1+6]=bytes((16,32,64,16,16,16))
                    data[p2:p2+6]=bytes((18,19,24,4,4,4))
                    data[timing:timing+6]=bytes((3,4,5,0,0,0))
        for pattern in range(16):
            data[ot_bank.PTRN_BASE+pattern*ot_bank.PTRN_STRIDE+ot_bank.PTRN_STRIDE-5]=0
            for track in range(8):
                off=otp.trac_off(pattern,track)
                data[off:off+64]=bytes(64)
                data[off+0x59:off+0x59+64*32]=bytes([255])*(64*32)
                if pattern==0: data[off+7]=1  # Eight voices start together.
    otp._bank_write(project,1,populate,guard=False)
    payload=bytearray()
    for part in range(8):
        for lane in range(48):
            pulses=(1,8,16)[(part+lane)%3]
            payload.extend((16,pulses,lane%16,(part+lane)%8,127,127,pulses,0,127,30))
    header=b'EULF'+struct.pack('>II',1,3840)
    (project/'eulf01.work').write_bytes(header+struct.pack('>I',zlib.crc32(header+payload))+payload)
    run(['make','bus','REMIX=euclid-lfo'],out/'build.log')
    image=out/'mainos.bin'; shutil.copy2(ROOT/'out/mainos_bus.bin',image)
    nm=subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True)
    symbols={s[2]:int(s[0],16) for line in nm.splitlines() if len(s:=line.split())==3}
    card=out/'input.img'
    run([ROOT/'.venv/bin/python3','tools/emu/ot_emu/stage_card.py',project,'EUCLID','LFO',
         '--tree',out/'tree','--out',card,
         '--audio',f'{project/stress_project.SAMPLE_REL}:LFO/{stress_project.SAMPLE_REL}'],out/'stage.log')
    blocks=out/'euclid.dump'
    common=[ROOT/'out/emu/ot_emu','--image',image,'--card',card,'--dsp',
            '--set','EUCLID','--project','LFO','--load-ms','90000',
            '--main-level','64','--block-dump',blocks,
            '--audio-out',out/'boot',  # Install DSP capture before scenario forks.
            # The port takes the first ISR instruction inside exception entry;
            # watch its second instruction and add that one entry instruction.
            '--watch-pc',f'{symbols["eul_audio"]:#x},{symbols["eul_midi"]:#x},0x4000aad4,0x4000d9a6']
    scenarios=[]
    for tag,waveform in (('stock',4),('euclid',19)):
        edits=[]
        for part in range(4):
            for track in range(8):
                for lane in range(3):
                    base=0x400e21e0+0x8ed80+part*0x18b2
                    for offset in (0x2f5+30*track,0x4eb+36*track):
                        edits.append(f'{base+offset+lane:#x}={waveform}')
        dumps=f'0x800010e8,672={out / (tag+"-audio.bin")};0x46c770e0,672={out / (tag+"-midi.bin")}'
        scenarios.extend(['--scenario',f'{out / (tag+".log")} --sequencer --internal-clock --frames {a.frames} '
            f'--step -:poke:{";".join(edits)} --step -:call:0x40009094,0,0 '
            f'--step 1000:call:0x4004a8a4,1 --mem-dump {dumps} --audio-out {out / tag}'
            +(f' --block-dump {blocks}' if tag=='euclid' else '')])
    (out/'inputs.json').write_text(json.dumps({'frames':a.frames,'symbols':symbols,'source_hashes':sources},indent=2)+'\n')
    run(common+scenarios,out/'boot.log')
    verify_run(out,a.frames,symbols,sources)


def verify_run(out,frame_count,symbols,sources):
    results={}
    for tag in ('stock','euclid'):
        text=(out/f'{tag}.log').read_text()
        frames=re.search(r'frames run : (\d+) since transport start \(target (\d+)\), run ended (\w+)',text)
        assert frames and frames.group(3)=='REACHED' and int(frames.group(1))>=frame_count, (tag,'frames',out)
        assert 'DID NOT RETURN' not in text and 'ILLEGAL' not in text, (tag,'native call failure',out)
        cpu=re.search(r'cpu\s+: (\d+) ColdFire instructions over the frames \((\d+) per frame',text)
        assert cpu, (tag,'CPU receipt missing',out)
        seen=[set(),set()]; intervals=[]; entry=None
        for match in re.finditer(r'\[\s*(\d+)\] at (0x[0-9a-f]+).*?\[sp .*?: (\S+) (\S+) (\S+)',text):
            tick,pc=int(match[1]),int(match[2],16)
            if pc==0x4000aad4: entry=tick-1
            elif pc==0x4000d9a6 and entry is not None:
                intervals.append(tick-entry); entry=None
            elif pc in (symbols['eul_audio'],symbols['eul_midi']):
                seen[int(pc==symbols['eul_midi'])].add(int(match[5],0))
        if tag=='euclid': assert seen==[set(range(24)),set(range(24))], ('missing active lanes',seen,out)
        else: assert seen==[set(),set()], ('stock comparison called EUCLID',seen,out)
        assert len(intervals)>=frame_count, (tag,'frame entry/exit traces',out)
        intervals=intervals[-frame_count:]
        with wave.open(str(out/f'{tag}_core0.wav'),'rb') as wav:
            assert wav.getsampwidth()==3 and wav.getframerate()==44100
            pcm=wav.readframes(wav.getnframes())
            assert any(pcm[-2000*wav.getnchannels()*3:]), (tag,'silent final main output',out)
        results[tag]={'instructions_per_frame':int(cpu[2]),'frame_isr_mean':sum(intervals)/len(intervals),
                      'frame_isr_peak':max(intervals),'active_lanes':[len(x) for x in seen]}
    classes=blockdump.classes(blockdump.read(out/'euclid.dump'))
    for track in range(1,9):
        assert any(recloop.track_audio(classes,track)[-2000:]), ('silent final FLEX input',track,out)
        assert any(recloop.readback_audio(classes,track)[-2000:]), ('silent final DSP chain',track,out)
    receipt={'scope':__doc__,'image_sha256':hashlib.sha256((out/'mainos.bin').read_bytes()).hexdigest(),
             'frames':frame_count,'source_hashes':sources,'results':results,
             'limits':'Port instruction clock; not hardware-cycle or arbitrary-remix headroom acceptance.'}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(f'PASS: eight FLEX voices, 48 native LFO lanes and a Part change: {out / "receipt.json"}',flush=True)
    print(json.dumps(results,indent=2),flush=True)


if __name__=='__main__': main()
