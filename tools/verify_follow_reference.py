#!/usr/bin/env python3
"""Build the author's Follow/Part State units at fixed reference addresses."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]


def build(out, loopback=False):
    def run(*args):
        subprocess.run(list(map(str,args)),check=True,stdout=subprocess.DEVNULL)
    units=[('midi-part-state','setup'),('midi-part-state','part'),('midi-part-state','part-copy'),
           ('midi-follow','midi_follow'),('midi-follow','response'),('midi-follow','register'),
           ('midi-follow','settings'),('midi-follow','page')]
    if loopback:units += [('midi-loopback',n) for n in ('loopback','producers','settings','page')]
    objects=[]
    for i,(module,name) in enumerate(units):
        folder=out/str(i);folder.mkdir()
        inc='.set HAVE_FOLLOW,1\n'
        if module=='midi-part-state':inc += '.set MP_DEFINE,1\n'
        if loopback:inc += '.set HAVE_LOOPBACK,1\n'
        (folder/'remix.inc').write_text(inc)
        obj=folder/'unit.o'
        defs=['--defsym','mp_copy_target=0x400d6bb8','--defsym','mp_init_target=0x400d6bbc'] if name=='part-copy' else []
        run('m68k-elf-as','-mcpu=54455','-I',folder,*defs,'-o',obj,ROOT/'modules'/module/(name+'.s'))
        objects.append(obj)
    run('m68k-elf-ld','-Ttext=0x40a955e0','--defsym=mp_copy_target=0x400d6bb8','--defsym=mp_init_target=0x400d6bbc','-o',out/'runtime.elf',*objects)
    run('m68k-elf-objcopy','-O','binary',out/'runtime.elf',out/'runtime.bin')
    data=(out/'runtime.bin').read_bytes()
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--measure',action='store_true',help='print reference measurements without changing the expected file')
    args=parser.parse_args();actual={}
    for name,loopback in [('follow',False),('follow-loopback',True)]:
        with tempfile.TemporaryDirectory(prefix='follow-reference-') as tmp:actual[name]=build(Path(tmp),loopback)
    if args.measure:print(json.dumps(actual,indent=2));return
    expected=json.loads((ROOT/'follow-reference.json').read_text())['artifacts']
    if actual!=expected:raise SystemExit('Follow author reference mismatch: '+json.dumps(actual))
    print('[ok] Follow/Part State and Follow/Loopback author references match')

if __name__=='__main__':main()
