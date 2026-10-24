#!/usr/bin/env python3
"""VOIC single-detent edits and bounds on two independent Supersaw tracks."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'tools/verify')]
import toolpath, lcd_view
from verify_supersaw_port import fixture


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project', type=Path, required=True)
    ap.add_argument('--name', required=True)
    args = ap.parse_args()
    work = ROOT/'out/supersaw-port'/args.name
    work.mkdir(parents=True, exist_ok=False)
    fixture(args.project, work, (2, 3), True, voices=4, filter_type=1)
    shutil.copy2(ROOT/'out/mainos_bus.bin', work/'candidate.bin')
    rows = ['0 key 0x32 down', '40 key 0x32 up',
            '200 key 0x24 down', '240 key 0x24 up']
    values = {2: 4, 3: 4}
    checks = []
    # Alternate tracks, visit every value, then turn beyond both bounds.
    edits = [(2,-1),(3,-1),(2,-1),(3,-1),(2,-1),(3,-1),
             (2,-1),(3,-1),(2,1),(3,1),(2,1),(3,1),
             (2,1),(3,1),(2,1),(3,1)]
    for i, (track, delta) in enumerate(edits):
        ms = 400+i*300
        key = 0x10+track
        rows += [f'{ms} key {key:#x} down', f'{ms+40} key {key:#x} up',
                 f'{ms+100} enc 2 {delta}']
        values[track] = max(1, min(4, values[track]+delta))
        for t, value in values.items():
            rows.append(f'{ms+200} wait {0x80000818+72*t:#x} {value:02x} eq 1')
        checks.append(dict(track=track+1, delta=delta, t3=values[2], t4=values[3]))
    rows.append('5300 quit')
    (work/'panel.script').write_text('\n'.join(rows)+'\n')
    cmd = [str(ROOT/'out/emu/ot_emu'), '--image', str(work/'candidate.bin'),
           '--card', str(work/'card.img'), '--set', 'OCTABAM', '--project', 'SYNTH',
           '--mkii', '--load-ms', '90000', '--dsp', '--internal-clock',
           '--live-script', str(work/'panel.script'), '--lcd', str(work/'lcd.bin'),
           '--mem-dump', f'0x80000810,576={work}/lanes.bin']
    (work/'command.json').write_text(json.dumps(cmd, indent=2)+'\n')
    with (work/'port.log').open('w') as log:
        result = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    log = (work/'port.log').read_text()
    assert result.returncode == 0 and 'ended on quit' in log, work/'port.log'
    assert not any(s in log for s in ('WAIT TIMEOUT', 'DID NOT RETURN', 'unimplemented opcode'))
    lanes = (work/'lanes.bin').read_bytes()
    assert lanes[2*72+8] == lanes[3*72+8] == 4
    plane = lcd_view.read_plane(work/'lcd.bin')
    lcd_view.png(lcd_view.composite(lcd_view.pixels(plane), plane), work/'lcd.png')
    receipt = dict(result='pass', image_sha256=hashlib.sha256((work/'candidate.bin').read_bytes()).hexdigest(),
                   checks=checks, independent_tracks=[3,4], single_detents=True,
                   lower_and_upper_bounds=True, hardware_tested=False)
    (work/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('[ok] Supersaw VOIC: single detents, 1..4 bounds and independent T3/T4 edits')


if __name__ == '__main__':
    main()
