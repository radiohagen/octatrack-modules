#!/usr/bin/env python3
"""Focused Euclid LFO engine, installed waveforms, native controls and LCD.

Builds the requested remix (default euclid-lfo). Native card/power-up acceptance has its
own gate; full panel/performance acceptance is not covered by this probe.
"""
import argparse
import hashlib
import json
import pathlib
import platform
import struct
import subprocess
import sys
import zlib

ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import toolpath  # noqa: E402,F401
OUT=ROOT/'out/euclid-lfo'

def run(args):
    r=subprocess.run([str(x) for x in args],cwd=ROOT,text=True,capture_output=True)
    if r.returncode:
        raise RuntimeError(f'{args}\n{r.stdout[-4000:]}\n{r.stderr[-4000:]}')
    return r.stdout

def lcd_previews():
    """Lossless, nearest-neighbour previews of the native rendered pixels.

    No image library or redraw approximations: keep the 115x64 PPM originals
    and hash them alongside their enlarged PNG presentation copies.
    """
    def chunk(tag,data):
        return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data))
    hashes={}
    for path in sorted(OUT.glob('*.ppm')):
        if not path.name.startswith(('style','stock-lfo-')): continue
        original=path.read_bytes()
        header,bounds,maximum,pixels=original.split(b'\n',3)
        assert (header,bounds,maximum)==(b'P6',b'115 64',b'255')
        assert len(pixels)==115*64*3
        rows=[]
        for y in range(64):
            row=b'\0'+b''.join(pixels[(y*115+x)*3:(y*115+x+1)*3]*4 for x in range(115))
            rows.extend([row]*4)
        png=(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',460,256,8,2,0,0,0))
             +chunk(b'IDAT',zlib.compress(b''.join(rows),9))+chunk(b'IEND',b''))
        path.with_suffix('.png').write_bytes(png)
        hashes[path.name]=hashlib.sha256(original).hexdigest()
    (OUT/'lcd-pixels.json').write_text(json.dumps(hashes,indent=2)+'\n')
    expected=json.loads((ROOT/'modules/euclid-lfo/ui-pixels.json').read_text())
    assert hashes==expected, 'Native LCD pixels changed; inspect original and extrema renders before updating ui-pixels.json'
    print(f'PASS: {len(hashes)} native LCD pixel regressions match the reviewed layout candidates')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('remix',nargs='?',default='euclid-lfo')
    a=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    print(run([sys.executable,'modules/euclid-lfo/generate_control.py','--check']),end='')
    run(['make','bus',f'REMIX={a.remix}'])
    cc=['cc']
    if sys.platform=='darwin': cc+=['-arch',platform.machine()]
    print(run(cc+['-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',
                  'modules/euclid-lfo/engine.c','modules/euclid-lfo/test_engine.c',
                  '-o',OUT/'engine-test']),end='')
    print(run([OUT/'engine-test']),end='')
    print(run(cc+['-std=c11','-O1','-Wall','-Wextra','-Werror',
                  '-fsanitize=address,undefined','-g',
                  'modules/euclid-lfo/engine.c','modules/euclid-lfo/storage.c',
                  'modules/euclid-lfo/retention.c',
                  'modules/euclid-lfo/lifecycle.c','modules/euclid-lfo/test_lifecycle.c',
                  '-o',OUT/'lifecycle-test']),end='')
    print(run([OUT/'lifecycle-test']),end='')
    import runpy
    old_store={}
    exec(run(['git','show','HEAD:modules/store/manifest.py']),old_store)
    new_store=runpy.run_path(str(ROOT/'modules/store/manifest.py'))
    clients=['PLOCKS P2','KITS','MIDI SCENES']
    for mask in range(8):
        selected={key for i,key in enumerate(clients) if mask&(1<<i)}
        assert old_store['store_inc'](selected)==new_store['store_inc'](selected)
    print('PASS: STORE assembly includes unchanged for every combination of existing clients')
    from remix import ledger, registry
    modules=registry.modules()
    collisions=ledger.check([modules[key] for key in ('EUCLID LFO','STORE','PLOCKS P2')])
    assert any('SRAM' in item and 'euclid-lfo' in item and 'plocks' in item for item in collisions), collisions
    for key in ('KITS','MIDI SCENES'):
        assert not any('SRAM' in item for item in ledger.check([modules[k] for k in ('EUCLID LFO','STORE',key)]))
    print('PASS: SRAM ledger rejects PLOCKS P2 overlap; KITS/MIDI Scenes allocations do not overlap')
    print(run(cc+['-std=c11','-O1','-Wall','-Wextra','-Werror',
                  '-fsanitize=address,undefined','-g',
                  'modules/euclid-lfo/engine.c','modules/euclid-lfo/storage.c',
                  'modules/euclid-lfo/test_storage.c','-o',OUT/'storage-test']),end='')
    fixture=OUT/'storage-v1.bin'
    print(run([OUT/'storage-test',fixture]),end='')
    encoded=fixture.read_bytes()
    expected=bytearray()
    for part in range(8):
        for lane in range(48):
            steps=1+(part*7+lane)%16
            pulses=(part+lane)%(steps+1)
            expected.extend((steps,pulses,lane%steps,(part+lane)%8,
                             (part*19+lane)%128,(part*23+lane)%128,
                             lane%(pulses+1),part%pulses if pulses else 0,
                             (part*31+lane)%128,(part+lane)%31))
    assert encoded[:12]==b'EULF'+struct.pack('>II',1,3840)
    assert encoded[16:]==expected, 'Part/lane/field order changed'
    assert struct.unpack_from('>I',encoded,12)[0]==zlib.crc32(encoded[:12]+encoded[16:])
    # Recompute a valid checksum around malformed records: CRC alone must not
    # make bad parameter counts, future versions or a lying length acceptable.
    invalid=OUT/'storage-invalid.bin'
    cases=[(4,struct.pack('>I',2)),(8,struct.pack('>I',3830)),(0,b'NOPE')]
    last=16+7*480+47*10
    cases += [(last+field,bytes([255])) for field in range(10)]
    cases += [(last,b'\x00'), (last+3,b'\x08'), (last,bytes([8,0,0,0,0,0,0,1,0,0]))]
    for offset,replacement in cases:
        forged=bytearray(encoded)
        forged[offset:offset+len(replacement)]=replacement
        struct.pack_into('>I',forged,12,zlib.crc32(forged[:12]+forged[16:]))
        invalid.write_bytes(forged)
        run([OUT/'storage-test','--refuse',invalid])
    print('PASS: independent v1 byte/CRC oracle; future and malformed CRC-valid files refused')
    stock=(ROOT/'out/raw/section_3_MAIN_OS.bin').read_bytes()
    image=(ROOT/'out/mainos_bus.bin').read_bytes()
    image_base=0x40000400
    for start,end in ((0x4003932c,0x40039528),(0x40054cd8,0x40055000)):
        assert image[start-image_base:end-image_base]==stock[start-image_base:end-image_base], 'Native RATE writer changed by another module; combination needs qualification'
    for address in (0x400d6210,0x400d6290):
        offset=address-image_base
        assert image[offset:offset+19*4]==stock[offset:offset+19*4], 'stock waveform changed'
        assert image[offset+20*4:offset+32*4]==stock[offset+20*4:offset+32*4], 'padding changed'
    for address in (0x400d38ac,0x400d4218):
        assert struct.unpack_from('>I',image,address-image_base)[0]==20
    offset=0x400bdf36-image_base
    assert image[offset:offset+19*4]==stock[offset:offset+19*4], 'stock WAVE pictograms changed'
    assert struct.unpack_from('>I',image,0x400bdf82-image_base)[0], 'EUCLID WAVE pictogram is NULL'
    print('PASS: both waveform counts extended; all 19 original waveforms and unused slots preserved')
    run(['cmake','-S','tools/emu/ot_emu','-B','out/emu'])
    run(['cmake','--build','out/emu','--target','ot_euclid_lfo_test','-j8'])
    symbols={s[2]:int(s[0],16) for line in run(['m68k-elf-nm','out/platform/runtime/runtime.elf']).splitlines()
             if len(s:=line.split())==3}
    (OUT/'symbols.txt').write_text(''.join(f'{name} {value:x}\n' for name,value in symbols.items()))
    layout=json.loads((ROOT/'out/platform/layout.json').read_text())
    result=run(['out/emu/ot_euclid_lfo_test','out/mainos_bus.bin','out/platform/runtime.raw',
                f'{layout["base"]:x}',f'{symbols["eul_bank"]:x}',OUT,
                f'{symbols["eul_file_encode"]:x}',f'{symbols["eul_file_decode"]:x}'])
    (OUT/'probe.log').write_text(result)
    for line in result.splitlines():
        if line.startswith(('PASS:','COST:')): print(line)
    lcd_previews()
    receipt={'scope':'engine, native destination routing, codec, fault-injected lifecycle, Part callbacks/controls and LCD pixel regression',
             'remix':a.remix,
             'image_sha256':hashlib.sha256(image).hexdigest(),
             'runtime_sha256':hashlib.sha256((ROOT/'out/platform/runtime.raw').read_bytes()).hexdigest(),
             'instruction_costs':[line for line in result.splitlines() if line.startswith('COST:')],
             'separate_checks':['native filesystem/power-up card gate','full-panel UI/Part gate',
                                'DSP-loaded frame gate','make check'],
             'limits':'Software instruction counts and pixels, not physical hardware acceptance.'}
    (OUT/'focused-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')

if __name__=='__main__': main()
