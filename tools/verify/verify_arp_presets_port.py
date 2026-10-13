#!/usr/bin/env python3
"""Native panel selection, project save/reload and arp MIDI in the full port.

Runs only with --project / OT_PROJECT; stages an owned, silent fixture.
Uses the image-stage build; never writes the supplied project or a device.
"""
import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import toolpath  # noqa: E402,F401
import ab_fixture, emu_card, ot_project as otp  # noqa: E402
from remix import registry  # noqa: E402

OUT = ROOT / 'out/arp-presets-port'
DB = 0x400e21e0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('remix', nargs='?', default='arp-presets')
    ap.add_argument('--project', default=os.environ.get('OT_PROJECT', ''))
    ap.add_argument('--midi-only', action='store_true', help='run only the playback cases while iterating')
    a = ap.parse_args()
    if 'ARP PRESETS' not in registry.remix(a.remix).modules: return
    if not a.project:
        print('  [SKIP] ARP PRESETS panel/save/MIDI: set OT_PROJECT or --project'); return
    if not (ROOT / 'out/emu/ot_emu').is_file():
        raise SystemExit('ARP PRESETS port gate requires make emu-cf')
    OUT.mkdir(parents=True, exist_ok=True)
    project = ab_fixture.prepare(a.project, OUT / 'project')
    for f in project.glob('project.*'):
        raw = re.sub(rb'\[SAMPLE\].*?\[/SAMPLE\]\r?\n', b'', f.read_bytes(), flags=re.S)
        f.write_bytes(raw)
    # A single sustained root, no audio. The native arp determines output
    # rhythm; one trigger only in a 64-step pattern avoids a retrigger reset.
    for f in project.glob('bank*.work'):
        def mutate(data):
            for part in range(8):
                base = otp.PART_BASE + part * otp.PART_STRIDE + 9
                for track in range(8):
                    at = base + 0x3e2 + track * 32
                    data[at:at+32] = bytes.fromhex(
                        '3c 64 7f 40 40 40 20 20 20 00 00 00 40 00 02 05 '
                        '00 01 40 00 7f 00 00 40 00 00 00 00 00 00 00 00')
                    data[base + 0x4e2 + track * 36] = 1 if track == 0 else 0
                    data[base + 0x4e2 + track * 36 + 17] = 0  # KEY OFF
            for p in range(16):
                end = 0x16 + (p + 1) * 0x8eec
                data[end-11:end-6] = bytes((16, 2, 64, 2, 0))
                for track in range(8):
                    at = 0x492e + p * 0x8eec + track * 0x8b9
                    assert data[at:at+4] == b'MTRA'
                    data[at+9:at+33] = bytes(24)
                    data[at+0x39:at+0x839] = b'\xff' * 2048
                    if p == 0 and track == 0:
                        data[at+9:at+17] = (1).to_bytes(8, 'big')
        otp._bank_write(project, int(f.stem[4:]), mutate, guard=False)
    card, _ = emu_card.stage_project(project, 'ARPSET', 'ARPTEST', tree=OUT / 'tree')
    (OUT / 'card.img').write_bytes(card)
    shutil.copy2(ROOT / 'out/mainos_bus.bin', OUT / 'mainos.bin')
    nm = subprocess.check_output(['m68k-elf-nm', '--extern-only', '--defined-only', str(ROOT / 'out/platform/runtime/runtime.elf')], text=True)
    symbols = {p[2]: int(p[0], 16) for p in map(str.split, nm.splitlines()) if len(p) == 3}

    def run(tag, extra, card='card.img'):
        cmd = [ROOT / 'out/emu/ot_emu', '--image', OUT / 'mainos.bin', '--card', OUT / card,
               '--set', 'ARPSET', '--project', 'ARPTEST', '--mount', '--load-ms', '90000', '--mkii', *extra]
        with (OUT / f'{tag}.log').open('w') as log:
            result = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        assert result.returncode == 0, f'{tag}: see {OUT / (tag + ".log")}'

    if not a.midi_only:
        # Native panel entry and encoder reports, not just a call to ap_apply.
        t, lines = 1500, []

        def tap(key, gap=300):
            nonlocal t
            lines.extend((f'{t} key {key:#x} down', f'{t+40} key {key:#x} up')); t += gap

        tap(0x32); tap(0x35)
        lines.append(f'{t} key 0x2d down'); t += 50
        tap(0x23); lines.append(f'{t} key 0x2d up'); t += 300
        for _ in range(4): lines.append(f'{t} enc 0 1'); t += 300
        ui = lines + [f'{t+400} quit']
        (OUT / 'ui.script').write_text('\n'.join(ui) + '\n')
        seed = ['--step', '-:poke:0x100b14cc=0;0x100b14cf=0', '--step', f'-:call:{symbols["ap_apply"]:#x},0']
        run('ui', [*seed, '--live-script', OUT / 'ui.script', '--lcd', OUT / 'lcd.bin',
                   '--mem-dump', f'{DB:#x},635712={OUT / "ui.bank"};0x10000000,1048576={OUT / "ui.cs1"}'])
        bank = (OUT / 'ui.bank').read_bytes()

        def arp(b): return b[0x8f270:0x8f271] + b[0x905a2:0x905a4] + b[0x905b2:0x905c2]

        expected = b'\x07\x00\x49' + bytes(16)
        assert arp(bank) == expected, 'panel A did not select tresillo'
        cs = (OUT / 'ui.cs1').read_bytes()
        assert cs[0xa53be] == 7 and cs[0xa66f0:0xa66f2] == b'\0I'
        assert cs[0xa6700:0xa6710] == bytes(16)
        # Render the actual LCD plane; the test asserts data, human QA checks pixels.
        subprocess.run([sys.executable, str(ROOT / 'tools/emu/lcd_view.py'), str(OUT / 'lcd.bin'),
                        '--png', str(OUT / 'arp-presets.png')], check=True)
        print('  [PASS] native FUNC+AMP and A reports load tresillo in Part and retained SRAM', flush=True)

        if 'MIDI SCALES' in registry.remix(a.remix).modules:
            # Same editor, both installed detours: OFF -> C major -> C Dorian,
            # then load CINQUIL with A without touching the extended KEY.
            script = lines + [f'{t+200} enc 5 4', f'{t+500} enc 5 4',
                              f'{t+800} enc 0 1', f'{t+1400} quit']
            (OUT / 'scales.script').write_text('\n'.join(script) + '\n')
            run('scales', [*seed, '--live-script', OUT / 'scales.script',
                           '--lcd', OUT / 'scales.lcd', '--mem-dump',
                           f'{DB:#x},635712={OUT / "scales.bank"};0x10000000,1048576={OUT / "scales.cs1"}'])
            b = (OUT / 'scales.bank').read_bytes()
            c = (OUT / 'scales.cs1').read_bytes()
            assert b[0x8f273] == 25 and c[0xa53c1] == 25, 'F did not select C Dorian'
            assert arp(b) == b'\x07\x00\x6d' + bytes(16), 'A changed KEY or failed to load cinquillo'
            subprocess.run([sys.executable, str(ROOT / 'tools/emu/lcd_view.py'),
                            str(OUT / 'scales.lcd'), '--png', str(OUT / 'arp-scales.png')], check=True)
            print('  [PASS] combined panel: F selects C Dorian; A loads cinquillo while preserving extended KEY', flush=True)

        # Close SETUP and capture the fixture's SPD 6 as 1/16 through the
        # real descriptor and LCD. The linked-code gate checks all labels.
        for tag in ('sixteenth',):
            script = lines + [f'{t+100} key 0x32 down', f'{t+140} key 0x32 up',
                              f'{t+500} key 0x23 down', f'{t+540} key 0x23 up',
                              f'{t+1600} quit']
            (OUT / f'speed-{tag}.script').write_text('\n'.join(script) + '\n')
            run(f'speed-{tag}', [*seed, '--live-script', OUT / f'speed-{tag}.script',
                                '--lcd', OUT / f'speed-{tag}.lcd'])
            subprocess.run([sys.executable, str(ROOT / 'tools/emu/lcd_view.py'),
                            str(OUT / f'speed-{tag}.lcd'), '--png', str(OUT / f'speed-{tag}.png')], check=True)

        # Browse from tresillo to the new final preset using actual A reports.
        # Its leading rest and omitted kick beats must survive native save/load.
        for _ in range(12): lines.append(f'{t} enc 0 1'); t += 300
        (OUT / 'kentbass.script').write_text('\n'.join(lines + [f'{t+400} quit']) + '\n')
        run('kentbass-ui', [*seed, '--live-script', OUT / 'kentbass.script',
                           '--lcd', OUT / 'kentbass.lcd', '--mem-dump',
                           f'{DB:#x},635712={OUT / "kentbass.bank"}'])
        expected = b'\x0f\xa4\x4a' + bytes(16)
        assert arp((OUT / 'kentbass.bank').read_bytes()) == expected, 'A did not select offbeat-only KENTBASS'
        subprocess.run([sys.executable, str(ROOT / 'tools/emu/lcd_view.py'),
                        str(OUT / 'kentbass.lcd'), '--png', str(OUT / 'kentbass.png')], check=True)
        print('  [PASS] native A selects KENTBASS: steps 2/4/7/11/14/16, no kick positions or offsets', flush=True)

        # Close ARP, then use the native SAVE PROJECT menu and confirmation.
        tap(0x32); tap(0x1c, 1000); tap(0x21, 700); tap(0x20, 500)
        tap(0x31, 1100); tap(0x31, 30000)
        lines.append(f'{t} quit')
        (OUT / 'save.script').write_text('\n'.join(lines) + '\n')
        run('save', [*seed, '--live-script', OUT / 'save.script', '--card-out', OUT / 'saved.img'])
        run('reload', ['--mem-dump', f'{DB:#x},635712={OUT / "reload.bank"}'], 'saved.img')
        assert arp((OUT / 'reload.bank').read_bytes()) == expected, 'native SAVE PROJECT/cold LOAD lost the arp'
        print('  [PASS] native SAVE PROJECT and cold LOAD PROJECT preserve the editable arp', flush=True)

    # Full native arp/MIDI path: compare two rhythms and switch a sounding
    # sustained root to an octave preset without injecting a new note trig.
    # 9600 frames of 16 samples at 44.1 kHz cover 3.48 s: 28 arp ticks at
    # 120 BPM / SPD 6, long enough to see multiple eight-tick cycles.
    for tag, preset, switch in (('straight', 0, False), ('tresillo', 4, False),
                                ('kentbass', 16, False), ('switch', 4, True)):
        extra = ['--step', '-:poke:0x100b14cc=0;0x100b14cf=0',
                 '--step', f'-:call:{symbols["ap_apply"]:#x},{preset}',
                 '--sequencer', '--internal-clock', '--frames', '9600',
                 '--midi-out', OUT / f'{tag}.midi']
        if switch: extra += ['--step', f'4000:call:{symbols["ap_apply"]:#x},15']
        run(tag, extra)
    def ons(path):
        status, data, notes = 0, [], []
        active = set()
        for v in path.read_bytes():
            if v >= 0xf8: continue
            if v & 128: status, data = v, []; continue
            if not 0x80 <= status < 0xf0: continue
            data.append(v)
            if len(data) == (1 if status & 0xf0 in (0xc0, 0xd0) else 2):
                if status == 0x90 and data[1]:
                    assert data[0] not in active, ('duplicate note-on', path, data)
                    active.add(data[0]); notes.append(data[0])
                elif status == 0x80 or (status == 0x90 and not data[1]):
                    assert data[0] in active, ('unmatched note-off', path, data)
                    active.remove(data[0])
                data = []
        assert not active, ('unreleased notes at end of capture', path, active)
        return notes
    straight, tresillo, switched = [ons(OUT / f'{tag}.midi') for tag in ('straight', 'tresillo', 'switch')]
    assert len(straight) == 28 and set(straight) == {60}, straight
    assert len(tresillo) == 11 and set(tresillo) == {60}, tresillo
    kentbass = ons(OUT / 'kentbass.midi')
    assert len(kentbass) == 10 and set(kentbass) == {60}, kentbass
    assert set(switched) == {60, 72}, switched
    print(f'  [PASS] native MIDI: {len(straight)} straight / {len(tresillo)} tresillo / {len(kentbass)} kentbass onsets; held-root switch reaches +12; balanced releases', flush=True)


if __name__ == '__main__': main()
