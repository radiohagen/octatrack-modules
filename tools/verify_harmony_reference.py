#!/usr/bin/env python3
"""Independent author build of Harmony, native Part access and retention."""
import argparse,hashlib,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def build(out,layout):
    spec=json.loads((ROOT/'harmony-reference.json').read_text())
    units=[('midipartsetup','modules/midi-part-state/setup.s'),('midipart','modules/midi-part-state/part.s'),('midipartcopy','modules/midi-part-state/part-copy.s'),*spec['units']]
    if layout!='LEGACY':units.insert(3,('midisram','modules/midi-sram/pool.s'))
    if layout=='MIDI TRACK':
        units=[(k,'modules/midi-harmony/degrees/storage-track.s' if k=='degreestorage' else p) for k,p in units]
        units += [('degreetrack','modules/midi-harmony/degrees/track-retention.s')]
    objects=[]
    for i,(label,path) in enumerate(units):
        folder=out/str(i);folder.mkdir();inc=''
        if label=='midipartsetup':inc='.set HAVE_HARMONY,1\n'
        if label in ('midipart','midipartcopy'):inc='.set MP_DEFINE,1\n'
        if label=='midipartcopy':inc+='.set HAVE_HARMONY,1\n'+('.set HAVE_MIDI_SRAM,1\n' if layout!='LEGACY' else '')
        if label=='chordfiles' and layout=='MIDI TRACK':inc='.set HD_TRACK_SRAM,1\n'
        if label=='degreeaccess':inc='.set HD_FOLLOW,0\n.set HD_SCALES,0\n.set HD_SCENES,0\n'
        if label=='degreesceneaccess':inc='.set HD_SCENES,0\n'
        if label=='degreepool':
            base={'LEGACY':0x100fd560,'SHARED':0x100f8620,'MIDI TRACK':0x1001aa6c}[layout]
            inc=f'.global hd_nv_base\n.set hd_nv_base,0x{base:x}\n'
        (folder/'remix.inc').write_text(inc)
        obj=folder/'unit.o'
        defs=['--defsym','mp_copy_target=0x400d6bb8','--defsym','mp_init_target=0x400d6bbc'] if label=='midipartcopy' else []
        subprocess.run(['m68k-elf-as','-mcpu=54455','-I',str(folder),*defs,'-o',str(obj),str(ROOT/path)],check=True)
        objects.append(str(obj))
    subprocess.run(['m68k-elf-ld','-Ttext='+spec['runtime_address'],'--defsym=mp_copy_target=0x400d6bb8','--defsym=mp_init_target=0x400d6bbc','-o',str(out/'runtime.elf'),*objects],check=True)
    subprocess.run(['m68k-elf-objcopy','-O','binary',str(out/'runtime.elf'),str(out/'runtime.bin')],check=True)
    data=(out/'runtime.bin').read_bytes()
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--measure',action='store_true');a=ap.parse_args();actual={}
    for layout in ('LEGACY','SHARED','MIDI TRACK'):
        with tempfile.TemporaryDirectory(prefix='harmony-reference-') as tmp:actual[layout]=build(Path(tmp),layout)
    if a.measure:print(json.dumps(actual,indent=2));return
    expected=json.loads((ROOT/'harmony-reference.json').read_text())['artifacts']
    if actual!=expected:raise SystemExit('Harmony author reference mismatch: '+json.dumps(actual))
    print('[ok] all three Harmony/Part State retention references match')
if __name__=='__main__':main()
