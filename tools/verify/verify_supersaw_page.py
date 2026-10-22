#!/usr/bin/env python3
"""Resolve Supersaw and ordinary FM pages through the installed native resolver."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import re
ROOT=Path(__file__).resolve().parents[2]
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--fixture',type=Path,required=True)
    args=ap.parse_args()
    fixture=args.fixture
    out=ROOT/'out/supersaw-page';out.mkdir(parents=True,exist_ok=True)
    raw=subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/supersaw-frozen/runtime.elf')],text=True)
    sym={f[2]:int(f[0],16) for line in raw.splitlines() if len(f:=line.split())==3}
    cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(ROOT/'out/supersaw-frozen/candidate.bin'),
         '--card',str(fixture/'card.img'),'--set','OCTABAM','--project','SYNTH',
         '--mkii','--load-ms','90000','--dsp','--sequencer','--internal-clock','--frames','1',
         '--step','-:call:0x40031da4,1,0',
         '--step',f'-:dump:{sym["ss_descriptor"]:#x},402={out}/supersaw.bin',
         '--step','-:call:0x40031da4,5,0',
         '--step',f'-:dump:{sym["po_pgdesc_buf"]:#x},402={out}/fm.bin']
    with (out/'port.log').open('w') as log:
        result=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=600)
    text=(out/'port.log').read_text();assert result.returncode==0 and 'DID NOT RETURN' not in text
    addresses=[int(x,16) for x in re.findall(r'call\s+: 0x40031da4\(2 args\) returned, d0 = (0x[0-9a-f]+)',text)]
    assert addresses==[sym['ss_descriptor'],sym['po_pgdesc_buf']],addresses
    supersaw=(out/'supersaw.bin').read_bytes();fm=(out/'fm.bin').read_bytes()
    assert supersaw[9:18]==b'SUPERSAW\0'
    assert fm[9:18]==b'FM SYNTH\0'
    for i,name in enumerate(('PTCH','DETU','MORF','CUT','SUB','DRIV')):
        assert supersaw[0x16+6*i:0x1c+6*i]==name.encode().ljust(6,b'\0'),(i,supersaw.hex())
    for i,name in enumerate(('PTCH','RATO','INDX','FINE','FDBK','DEC')):
        assert fm[0x16+6*i:0x1c+6*i]==name.encode().ljust(6,b'\0'),(i,fm.hex())
    print('[ok] native resolver returns separate Supersaw/FM descriptors and correct knob labels')
    (out/'receipt.json').write_text(json.dumps(dict(image_sha256=hashlib.sha256((ROOT/'out/supersaw-frozen/candidate.bin').read_bytes()).hexdigest(),descriptors=addresses,native_resolver=True,hardware_tested=False,command=cmd),indent=2)+'\n')
if __name__=='__main__':main()
