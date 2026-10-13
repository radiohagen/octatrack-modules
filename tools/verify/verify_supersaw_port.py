#!/usr/bin/env python3
"""Supersaw on the real combined firmware with FM, Sophie or another Supersaw."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import verify_synth_bus_port as fm
ROOT = fm.ROOT
ORIGINAL = fm.fixture
MODE = 'fm'
RICH = False

def fixture(source, work, sequenced, voices, loopback=False):
    ORIGINAL(source, work, sequenced, voices, loopback)
    project = work/'project'
    for path in project.glob('project.*'):
        raw = path.read_bytes()
        for slot in (2,3):
            raw = re.sub(rb'\[SAMPLE\]\r\nTYPE=FLEX\r\nSLOT=00'+str(slot).encode()+rb'\r\n.*?\[/SAMPLE\]\r\n\r\n',b'',raw,flags=re.S)
        records = b''
        for slot, name in ((2,'SUPERSAW'),(3,'SOPHIE')):
            records += (f'[SAMPLE]\r\nTYPE=FLEX\r\nSLOT={slot:03d}\r\nPATH=../AUDIO/FMSYNTH-{name}.wav\r\n'
                'TRIM_BARSx100=100\r\nLOOP_BARSx100=100\r\nBPMx24=2880\r\nTSMODE=2\r\n'
                'LOOPMODE=1\r\nGAIN=48\r\nTRIGQUANTIZATION=-1\r\n[/SAMPLE]\r\n\r\n').encode()
        pos = raw.index(b'[SAMPLE]'); path.write_bytes(raw[:pos]+records+raw[pos:])
    for path in project.glob('markers.*'):
        raw = bytearray(path.read_bytes())
        for slot in (1,2): raw[0x16+784*slot:0x16+784*(slot+1)] = raw[0x16:0x16+784]
        raw[-2:] = (sum(raw[0x10:-2])&65535).to_bytes(2,'big'); path.write_bytes(raw)
    assignments = {1:1} if MODE == 'fm' else {1:2,5:1} if MODE == 'sophie' else {1:1,5:1}
    for bank in project.glob('bank*.work'):
        def edit(data):
            for part in range(8):
                base = fm.otp.PART_BASE+part*fm.otp.PART_STRIDE+9
                for track,slot in assignments.items():
                    data[base+0x2ca+5*track+1] = slot
                    at = base+0x2a+30*track+6
                    params = (64,50,0,64,0,64) if slot == 2 else (64,96,110,64,40,30) if RICH else (64,0,0,64,0,0)
                    data[at:at+6] = bytes(params)
        fm.otp._bank_write(project,int(bank.stem[4:]),edit,guard=False)
    card,_ = fm.emu_card.stage_project(project,'OCTABAM','SYNTH',tree=work/'tree-supersaw',
        audio=[f'{fm.OUT}/FMSYNTH.wav:AUDIO/{name}.wav' for name in
               ('FMSYNTH','FMSYNTH-SUPERSAW','FMSYNTH-SOPHIE')])
    (work/'card.img').write_bytes(card)

def main():
    global MODE,RICH
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project',required=True,type=Path)
    ap.add_argument('--mode',choices=('fm','sophie','dual'),default='fm')
    ap.add_argument('--case',choices=('midi-mono','sequence','loopback'),default='midi-mono')
    ap.add_argument('--rich',action='store_true')
    args = ap.parse_args(); MODE=args.mode; RICH=args.rich
    fm.OUT = ROOT/f'out/supersaw-port/{MODE}-{args.case}-{int(RICH)}'
    fm.OUT.mkdir(parents=True,exist_ok=True);fm.fixture=fixture
    (fm.OUT/'candidate.bin').write_bytes((ROOT/'out/mainos_bus.bin').read_bytes())
    raw = subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True)
    sym = {f[2]:int(f[0],16) for line in raw.splitlines() if len(f:=line.split())==3}
    fm.marker(fm.OUT/'FMSYNTH.wav'); work=fm.OUT/args.case
    keys = ['ss_samples','ss_unsupported'] + (['sf_samples','sf_unsupported'] if 'sf_samples' in sym else [])
    dumps = [f'{sym[k]:#x},32={work}/{k}.bin' for k in keys]
    result = fm.run_case(args.project,args.case,sym,sequenced=args.case=='sequence',check_pitch=not RICH,extra_dumps=dumps)
    expected_ss = {1} if MODE=='fm' else {5} if MODE=='sophie' else {1,5}
    expected_sf = {1} if MODE=='sophie' else set()
    for name,expected in (('ss',expected_ss),('sf',expected_sf)):
        if name+'_samples' not in sym:
            assert not expected, 'Sophie mode requires SOPHIE selected'
            continue
        counts = struct.unpack('>8I',(work/(name+'_samples.bin')).read_bytes())
        assert all(n>16000 if t in expected else n==0 for t,n in enumerate(counts)),(name,expected,counts)
        assert (work/(name+'_unsupported.bin')).read_bytes()==bytes(32)
        result[name+'_samples_per_track'] = counts
    result.update(mode=MODE,rich=RICH,hardware_tested=False,image_sha256=hashlib.sha256((fm.OUT/'candidate.bin').read_bytes()).hexdigest())
    (fm.OUT/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print('[ok] Supersaw coexistence',MODE,args.case,'rich',RICH)
if __name__=='__main__': main()
