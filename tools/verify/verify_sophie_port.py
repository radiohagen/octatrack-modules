#!/usr/bin/env python3
"""Sophie + FM + full personal remix: both DSP cores, release and bus routing.

Reuses the existing full-firmware synth fixture and assertions; switches only
one marker track to Sophie. Original projects/cards are never written.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import verify_synth_bus_port as fm

ROOT=fm.ROOT
ORIGINAL_FIXTURE=fm.fixture
SOPHIE_TRACK=1
METAL=0
FINE=0


def fixture(source, work, sequenced, voices, loopback=False, harmony=True):
    ORIGINAL_FIXTURE(source,work,sequenced,voices,loopback,harmony)
    project=work/'project'
    for path in project.glob('project.*'):
        raw=path.read_bytes()
        raw=re.sub(rb'\[SAMPLE\]\r\nTYPE=FLEX\r\nSLOT=002\r\n.*?\[/SAMPLE\]\r\n\r\n',b'',raw,flags=re.S)
        marker=(b'[SAMPLE]\r\nTYPE=FLEX\r\nSLOT=002\r\nPATH=../AUDIO/FMSYNTH-SOPHIE.wav\r\n'
                b'TRIM_BARSx100=100\r\nLOOP_BARSx100=100\r\nBPMx24=2880\r\nTSMODE=2\r\n'
                b'LOOPMODE=1\r\nGAIN=48\r\nTRIGQUANTIZATION=-1\r\n[/SAMPLE]\r\n\r\n')
        pos=raw.index(b'[SAMPLE]');path.write_bytes(raw[:pos]+marker+raw[pos:])
    # Copy the existing valid trim/loop marker settings to the new FLEX slot.
    # verify_repitch documents the 0x16 header and 784 sample records.
    for path in project.glob('markers.*'):
        data=bytearray(path.read_bytes());data[0x16+784:0x16+2*784]=data[0x16:0x16+784];data[-2:]=(sum(data[0x10:-2])&65535).to_bytes(2,'big');path.write_bytes(data)
    for bank in project.glob('bank*.work'):
        def edit(data):
            for part in range(8):
                base=fm.otp.PART_BASE+part*fm.otp.PART_STRIDE+9
                data[base+0x2ca+5*SOPHIE_TRACK+1]=1
                at=base+0x2a+30*SOPHIE_TRACK+6
                data[at:at+6]=bytes((64,50,METAL,64+FINE,0,64))
        fm.otp._bank_write(project,int(bank.stem[4:]),edit,guard=False)
    card,_=fm.emu_card.stage_project(project,'OCTABAM','SYNTH',tree=work/'tree-sophie',audio=[
        f'{fm.OUT}/FMSYNTH.wav:AUDIO/FMSYNTH.wav',
        f'{fm.OUT}/FMSYNTH.wav:AUDIO/FMSYNTH-SOPHIE.wav'])
    (work/'card.img').write_bytes(card)


def main():
    global SOPHIE_TRACK,METAL,FINE
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project',required=True,type=Path)
    ap.add_argument('--track',type=int,choices=(2,6),default=2)
    ap.add_argument('--metal',type=int,default=0)
    ap.add_argument('--fine',type=int,default=0,choices=range(-64,64),metavar='CENTS')
    ap.add_argument('--case',choices=('sequence','midi-mono','loopback'),default='midi-mono')
    ap.add_argument('--no-harmony',action='store_true')
    args=ap.parse_args();SOPHIE_TRACK=args.track-1;METAL=args.metal;FINE=args.fine
    fine_suffix=f'-fine{FINE}' if FINE else ''
    fm.OUT=ROOT/f'out/sophie-port/t{args.track}-{args.case}-metal{METAL}{fine_suffix}'
    fm.OUT.mkdir(parents=True,exist_ok=True);fm.fixture=fixture
    (fm.OUT/'candidate.bin').write_bytes((ROOT/'out/mainos_bus.bin').read_bytes())
    raw=subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True)
    sym={f[2]:int(f[0],16) for line in raw.splitlines() if len(f:=line.split())==3}
    fm.marker(fm.OUT/'FMSYNTH.wav')
    # Neutral FUSE is pitched; metallic spectra deliberately are not measured
    # with a single-tone zero-crossing estimator. The gate still tests energy,
    # release, both bus hosts, routing IDs and concurrent Harmony.
    case_dir=fm.OUT/args.case
    result=fm.run_case(args.project,args.case,sym,sequenced=args.case=='sequence',
                       harmony=not args.no_harmony,
                       check_pitch=not METAL and not FINE,extra_dumps=(
                         f'{sym["sf_samples"]:#x},32={case_dir}/sophie-samples.bin',
                         f'{sym["sf_unsupported"]:#x},32={case_dir}/sophie-unsupported.bin'))
    counts=struct.unpack('>8I',(case_dir/'sophie-samples.bin').read_bytes())
    assert counts[SOPHIE_TRACK]>16000, ('Sophie renderer not exercised',counts)
    assert all(n==0 for t,n in enumerate(counts) if t!=SOPHIE_TRACK), ('Sophie leaked onto ordinary tracks',counts)
    assert (case_dir/'sophie-unsupported.bin').read_bytes()==bytes(32)
    if not METAL and FINE and args.case=='midi-mono':
        measured=result['audio'][f'T{args.track}']['pitch_hz']
        expected=261.6256*math.pow(2,FINE/1200)
        assert abs(measured-expected)<2, ('Sophie FINE pitch',FINE,measured,expected)
    result['sophie_samples_per_track']=counts
    result.update(sophie_track=args.track,metal=METAL,fine_cents=FINE,hardware_tested=False,
                  image_sha256=hashlib.sha256((fm.OUT/'candidate.bin').read_bytes()).hexdigest())
    (fm.OUT/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print('[ok] Sophie alongside FM and full standard remix',args.track,args.case)
if __name__=='__main__':main()
