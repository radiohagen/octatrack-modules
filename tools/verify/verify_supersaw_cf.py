#!/usr/bin/env python3
"""Compare linked ColdFire arithmetic against the sanitizer-checked host engine."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[2]
CASES = ((21426141,0,0,0,0), (21426141,127,127,0,0),
         (21426141,96,110,40,30), (1024,127,127,127,127),
         (0xffffffff,127,127,127,127), (42726141,65,100,127,90))
PHASES = (0xfffffff0,0x12345678,0x87654321,0x7fffffff,0x80000000,0xabcdef01,0x3210fedc,0x11223344)
def main():
    frozen = ROOT/'out/supersaw-frozen'
    out = ROOT/'out/supersaw-cf';out.mkdir(parents=True,exist_ok=True)
    raw = subprocess.check_output(['m68k-elf-nm',str(frozen/'runtime.elf')],text=True)
    sym = {f[2]:int(f[0],16) for line in raw.splitlines() if len(f:=line.split())==3}
    source = '#include <stdio.h>\n#include "modules/supersaw/engine.c"\nint main(void) {\n'
    source += 'struct ss_voice v; int16_t out[32];\n'
    for case in CASES:
        source += 'v=(struct ss_voice){{'+','.join(str(p)+'u' for p in PHASES[:7])+'},'+str(PHASES[7])+'u};\n'
        source += '{struct ss_params p={'+','.join(str(p)+'u' for p in case)+'};ss_render(&v,&p,out,32);ss_render(&v,&p,out,32);fwrite(out,2,32,stdout);}\n'
    source += 'return 0;}\n'
    with tempfile.TemporaryDirectory() as tmp:
        c,exe = Path(tmp)/'oracle.c',Path(tmp)/'oracle';c.write_text(source)
        subprocess.run(['cc','-O2','-fsanitize=address,undefined','-I',str(ROOT),str(c),'-o',str(exe)],check=True)
        expected = struct.unpack('=192h',subprocess.check_output([str(exe)]))
    fixture = ROOT/'out/supersaw-port/fm-midi-mono-0/midi-mono/card.img'
    cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(frozen/'candidate.bin'),
         '--card',str(fixture),'--set','OCTABAM','--project','SYNTH',
         '--mkii','--load-ms','90000','--dsp','--sequencer','--internal-clock','--frames','1']
    sized = subprocess.check_output(['m68k-elf-nm','-S',str(frozen/'runtime.elf')],text=True)
    total = next(int(f[1],16) for line in sized.splitlines() if len(f:=line.split())==4 and f[3]=='ss_voices')
    assert total % 8 == 0
    stride = total // 8
    voice,params,output = sym['ss_voices'],sym['ss_voices']+7*stride,sym['ss_descriptor']
    for i,case in enumerate(CASES):
        data = [(voice,struct.pack('>8I',*PHASES)+bytes(stride-32)),(params,struct.pack('>IBBBB',*case))]
        poke=';'.join(f'{addr+n:#x}={v:#x}' for addr,values in data for n,v in enumerate(values))
        cmd += ['--step','-:poke:'+poke,'--step',f'-:call:{sym["ss_render"]:#x},{voice},{params},{output+i*64},32']
        cmd += ['--step',f'-:call:{sym["ss_render"]:#x},{voice},{params},{output+i*64},32']
    cmd += ['--mem-dump',f'{output:#x},384={out}/actual.bin']
    with (out/'port.log').open('w') as log:
        result=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    text=(out/'port.log').read_text()
    assert result.returncode==0 and 'LOAD PROJECT handled' in text and 'run ended REACHED' in text
    assert 'DID NOT RETURN' not in text and 'main never spun' not in text
    actual=struct.unpack('>192h',(out/'actual.bin').read_bytes())
    assert actual==expected,[(i,a,b) for i,(a,b) in enumerate(zip(actual,expected)) if a!=b][:10]
    (out/'receipt.json').write_text(json.dumps(dict(image_sha256=hashlib.sha256((frozen/'candidate.bin').read_bytes()).hexdigest(),
        cases=CASES,exact_samples=len(actual),hardware_tested=False,command=cmd),indent=2)+'\n')
    print('[ok] ColdFire matches host exactly: six patches, warm control cache, phase wrap, extreme pitches, 192 samples')
if __name__=='__main__':main()
