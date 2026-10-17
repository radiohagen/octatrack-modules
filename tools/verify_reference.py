#!/usr/bin/env python3
"""Reproduce the author's standalone linked source without firmware bytes."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def build(out):
    def run(*args):
        subprocess.run(list(map(str, args)), check=True, stdout=subprocess.DEVNULL)
    entry = ROOT / 'modules/midi-part-state/entry.s'
    run('m68k-elf-as', '-mcpu=5407', '-o', out/'entry.o', entry)
    units = [('midi-part-state', 'part'), ('midi-part-state', 'part-copy'),
             ('midi-loopback', 'loopback'), ('midi-loopback', 'producers'),
             ('midi-loopback', 'settings'), ('midi-loopback', 'page')]
    objects = []
    for i, (module, unit) in enumerate(units):
        folder = out/str(i)
        folder.mkdir()
        (folder/'remix.inc').write_text('.set MP_DEFINE,1\n' if module == 'midi-part-state' else '')
        obj = folder/'unit.o'
        defs = ['--defsym', 'mp_copy_target=0x400d6bb8', '--defsym', 'mp_init_target=0x400d6bbc'] if unit == 'part-copy' else []
        run('m68k-elf-as', '-mcpu=54455', '-I', folder, *defs, '-o', obj, ROOT/'modules'/module/(unit+'.s'))
        objects.append(obj)
    run('m68k-elf-ld', '-Ttext=0x40a955e0', '--defsym=mp_copy_target=0x400d6bb8',
        '--defsym=mp_init_target=0x400d6bbc', '-o', out/'runtime.elf', *objects)
    run('m68k-elf-objcopy', '-O', 'binary', out/'runtime.elf', out/'runtime.bin')
    # Resolve activation operands from the actual standalone runtime link.
    nm = subprocess.check_output(['m68k-elf-nm', str(out/'runtime.elf')], text=True)
    symbols = {f[2]: int(f[0],16) for line in nm.splitlines()
               if len(f := line.split()) == 3 and f[1] != 'U'}
    run('m68k-elf-ld', '-Ttext=0x400d6b80',
        '--defsym=mp_native_copy='+hex(symbols['mp_native_copy']),
        '--defsym=mp_native_init='+hex(symbols['mp_native_init']),
        '-o', out/'entry.elf', out/'entry.o')
    run('m68k-elf-objcopy', '-O', 'binary', out/'entry.elf', out/'entry.bin')
    return {name: {'bytes': len((out/(name+'.bin')).read_bytes()),
                   'sha256': hashlib.sha256((out/(name+'.bin')).read_bytes()).hexdigest()}
            for name in ('entry', 'runtime')}


def main():
    expected = json.loads((ROOT/'reference.json').read_text())['artifacts']
    with tempfile.TemporaryDirectory(prefix='midi-loopback-reference-') as tmp:
        actual = build(Path(tmp))
    if actual != expected:
        raise SystemExit('Author reference mismatch: '+json.dumps(actual, sort_keys=True))
    print('[ok] author runtime and cold-entry byte references match')


if __name__ == '__main__':
    main()
