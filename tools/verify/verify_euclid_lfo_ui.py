#!/usr/bin/env python3
"""Boot a clean copied project and exercise Euclid LFO via panel events.

No parameter/settings pokes: native WAVE selection, editor entry and edits
travel through UART panel dispatch. Screenshot candidates remain software
evidence, not physical LCD acceptance. The input project is never modified.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import toolpath  # noqa: E402,F401
sys.path.insert(0,str(ROOT/'tools/emu'))
import lcd_view  # noqa: E402
from verify_euclid_lfo_card import run  # noqa: E402


class Panel:
    def __init__(self):
        self.time=1500
        self.lines=[]

    def send(self,command,gap=400):
        self.lines.append(f'{self.time} {command}')
        self.time+=gap

    def tap(self,key,gap=400):
        self.send(f'key {key:#x} down',40)
        self.send(f'key {key:#x} up',gap)

    def encoder(self,index,delta,gap=400):
        self.send(f'enc {index} {delta}',gap)

    def hold(self,key,other,gap=700):
        self.send(f'key {key:#x} down',40)
        self.tap(other,100)
        self.send(f'key {key:#x} up',gap)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project',required=True,type=pathlib.Path)
    ap.add_argument('--only',help='comma-separated scenario names for a scoped rerun')
    ap.add_argument('--panel-model',choices=('mki','mkii'),default='mkii')
    a=ap.parse_args()
    selected=set(a.only.split(',')) if a.only else None
    part_cases=('seeded','save','reload','paste','undo','clear','switch')
    known={f'{kind}-page{page}' for kind in ('audio','midi') for page in (0,1)}
    known.update('part-'+operation for operation in part_cases)
    known.update(('audio-burst','midi-burst'))
    known.update(('audio-setup','midi-setup'))
    rates=((8,0),(16,0),(24,0),(32,0),(48,0),(64,0),(96,0),(64,1),(96,1),(64,2),(96,2),(64,3),(96,3),(64,1))
    known.update(f'{kind}-rate-{i}' for kind in ('audio','midi') for i in range(len(rates)))
    known.update(f'{kind}-free-{duration}' for kind in ('audio','midi') for duration in ('short','long'))
    if selected and not selected<=known: ap.error(f'unknown cases: {sorted(selected-known)}')
    for kind in ('audio','midi'):
        pair={f'{kind}-free-short',f'{kind}-free-long'}
        if selected and selected&pair and not pair<=selected:
            ap.error(f'FREE comparison needs both {kind} short and long cases')
    if not (a.project/'project.work').is_file() or not (a.project/'bank01.work').is_file():
        ap.error('--project needs project.work and bank01.work')
    parent=ROOT/'out/euclid-lfo-ui'; parent.mkdir(exist_ok=True)
    out=pathlib.Path(tempfile.mkdtemp(prefix='panel-',dir=parent))
    print(f'Native panel test: {out}',flush=True)
    project=out/'project'; project.mkdir()
    sources={}
    for source in sorted(a.project.glob('*.work')):
        if source.name.startswith('eulf'): continue
        shutil.copy2(source,project/source.name)
        sources[source.name]=hashlib.sha256(source.read_bytes()).hexdigest()
    run(['make','bus','REMIX=euclid-lfo'],out/'build.log')
    image=out/'mainos.bin'; shutil.copy2(ROOT/'out/mainos_bus.bin',image)
    nm=subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True)
    symbols={s[2]:int(s[0],16) for line in nm.splitlines() if len(s:=line.split())==3}
    card=out/'input.img'
    run([ROOT/'.venv/bin/python3','tools/emu/ot_emu/stage_card.py',project,'EUCLID','LFO',
         '--tree',out/'tree','--out',card],out/'stage.log')
    common=[ROOT/'out/emu/ot_emu','--image',image,'--card',card,
            '--set','EUCLID','--project','LFO','--load-ms','90000',
            '--lcd',out/'boot.lcd']  # Install pixel watches before scenario forks.
    if a.panel_model=='mkii': common.append('--mkii')
    scenarios=[]
    def add_case(name,p):
        if selected and name not in selected: return
        p.send('quit',0)
        script=out/f'{name}.script'; script.write_text('\n'.join(p.lines)+'\n')
        dump=';'.join(f'{address:#x},{size}={out / (name+"-"+label+".bin")}'
                      for address,size,label in ((symbols['eul_bank'],61440,'settings'),
                                                 (symbols['eul_editing'],4,'editing'),
                                                 (symbols['eul_page'],4,'page'),
                                                 (0x800010e8,672,'audio-state'),
                                                 (0x46c770e0,672,'midi-state'),
                                                 (0x400e21e0+0x8ed80,0x18b2,'native-part'),
                                                 (0x100a4ece,0x18b2,'native-sram'),
                                                 (0x80000002,1,'bank'),
                                                 (0x100b14cf,1,'part')))
        scenarios.extend(['--scenario',f'{out / (name+".log")} --live-script {script} '
                          f'--lcd {out / (name+".lcd")} --mem-dump {dump}'])
    for midi in (False,True):
        for index in range(len(rates)):
            p=Panel(); p.tap(0x32); p.tap(0x10)
            if midi: p.tap(0x35)
            p.tap(0x24,80); p.tap(0x24,700)
            p.encoder(6,-127); p.encoder(1,127)
            # Saved native SPD clamps at zero; index 13 tests leaving STOP.
            p.encoder(4,-127 if index==13 else 127)
            p.tap(0x31); p.tap(0x31)
            if index==13: p.encoder(5,1)
            else:
                p.encoder(5,-127)
                if index: p.encoder(5,index)
            add_case(('midi' if midi else 'audio')+f'-rate-{index}',p)
    for midi in (False,True):
        p=Panel(); p.tap(0x32); p.tap(0x10)
        if midi: p.tap(0x35)
        p.tap(0x24,80); p.tap(0x24,700)
        p.encoder(6,-127); p.encoder(1,127)
        add_case(('midi' if midi else 'audio')+'-setup',p)
        for page in (0,1):
            name=('midi' if midi else 'audio')+f'-page{page}'
            p=Panel(); p.tap(0x32); p.tap(0x10)
            if midi: p.tap(0x35)
            p.tap(0x24,80); p.tap(0x24,700)  # Native LFO SETUP.
            p.encoder(6,-127)               # Select first native LFO lane.
            p.encoder(1,127)                # WAVE clamps to appended EUCLID.
            p.tap(0x31,700)                 # Open our editor, no direct call.
            # Each control receives exactly one count; no injected settings.
            for encoder in range(6): p.encoder(encoder,1)
            if page:
                p.tap(0x31,700)
                p.encoder(4,1)              # DIR: POS -> NEG, one native count.
                p.encoder(5,-127)           # RATE minimum, independent of fixture SPD.
                p.encoder(5,7)              # Whole -> sixteenth (including triplets).
                p.send('key 0x3d down',40)  # Hold F: no native push acceleration.
                p.encoder(5,1)
                p.send('key 0x3d up',40)
                p.encoder(5,-1)
            add_case(name,p)
    for midi in (False,True):
        p=Panel(); p.tap(0x32); p.tap(0x10)
        if midi: p.tap(0x35)
        p.tap(0x24,80); p.tap(0x24,700)
        p.encoder(6,-127); p.encoder(1,127); p.tap(0x31,700)
        p.encoder(0,-127)  # Start at one step; eight fast counts must make nine.
        for _ in range(8): p.encoder(0,1,15)
        p.send('key 0x38 down',40)  # A push held during five reverse counts.
        for _ in range(5): p.encoder(0,-1,15)
        p.send('key 0x38 up',700)
        add_case(('midi' if midi else 'audio')+'-burst',p)
    for midi in (False,True):
        for duration,extra in (('short',0),('long',1700)):
            p=Panel(); p.tap(0x32); p.tap(0x10)
            if midi: p.tap(0x35)
            p.tap(0x24,80); p.tap(0x24,700)
            p.encoder(6,-127); p.encoder(1,127)
            p.encoder(3,-127)   # Native TRIG -> FREE, before entering our editor.
            p.encoder(4,16)     # Native SPD; no parameter poke or PLAY gesture.
            p.tap(0x31,700)
            p.time+=extra
            add_case(('midi' if midi else 'audio')+'-free-'+duration,p)
    # Native Part menus, seeded only through the editor. Each case begins
    # from the same clean boot; both audio and MIDI records must follow Parts.
    for operation in part_cases:
        p=Panel(); p.tap(0x32); p.tap(0x10)
        for midi in (False,True):
            if midi: p.tap(0x35)
            p.tap(0x24,80); p.tap(0x24,700)
            p.encoder(6,-127); p.encoder(1,127); p.tap(0x31,700)
            for encoder in range(6): p.encoder(encoder,1)
            if midi: p.encoder(0,1)
            p.tap(0x31); p.encoder(4,1)  # NEG is retained with the Part too.
            p.tap(0x32); p.tap(0x32)
        if operation in ('save','reload'):
            if a.panel_model=='mkii': p.hold(0x2d,0x1d)
            else:
                p.hold(0x2d,0x35); p.hold(0x2d,0x2f)  # MKI quick select, then edit.
            for _ in range(4): p.tap(0x33,100)
            p.tap(0x20); p.tap(0x20); p.tap(0x31,900)  # SAVE row.
            p.tap(0x32); p.tap(0x32)
            if operation=='reload':
                p.tap(0x24,80); p.tap(0x24,700); p.tap(0x31)
                p.encoder(0,3); p.tap(0x32); p.tap(0x32)
                p.hold(0x2d,0x2a,1300)  # FUNC+CUE -> saved Part (PANEL.md's measured map).
        if operation in ('paste','undo','clear','switch'):
            if a.panel_model=='mkii': p.tap(0x1d,700)
            else: p.hold(0x2d,0x35)
            p.hold(0x2d,0x29)     # FUNC+REC copies the selected Part.
            p.tap(0x21)          # Cursor Part 2, without linking it yet.
            p.hold(0x2d,0x27)    # FUNC+STOP pastes into Part 2; STOP is 0x27, not CUE 0x2a.
            if operation=='undo': p.hold(0x2d,0x27)
            elif operation=='clear': p.hold(0x2d,0x28)
            elif operation=='switch':
                p.tap(0x31,900)  # Link Part 2, then edit just its MIDI lane.
                p.tap(0x24,80); p.tap(0x24,700); p.tap(0x31)
                p.encoder(0,1); p.tap(0x32); p.tap(0x32)
        add_case('part-'+operation,p)
    run(common+scenarios,out/'boot.log')
    results={}
    for midi in (False,True):
        for index,(speed,mult) in enumerate(rates):
            name=('midi' if midi else 'audio')+f'-rate-{index}'
            if selected and name not in selected: continue
            assert 'ended on quit' in (out/f'{name}.log').read_text(),name
            for mirror in ('native-part','native-sram'):
                native=(out/f'{name}-{mirror}.bin').read_bytes()
                spd=int.from_bytes(native[0x3e8 if midi else 0x11a:][:1],'big',signed=True)
                assert spd==speed, (name,mirror,spd,speed)
                assert native[0x500 if midi else 0x30a]==mult, (name,mirror,'MULT')
            assert not any((out/f'{name}-settings.bin').read_bytes()), (name,'RATE wrote sidecar')
            results[name]={'native_speed':spd,'native_mult':mult,'part_and_sram_match':True}
    for kind in ('audio','midi'):
        name=kind+'-setup'
        if selected and name not in selected: continue
        log=(out/f'{name}.log').read_text()
        assert 'ended on quit' in log and 'WAIT TIMEOUT' not in log, name
        assert (out/f'{name}-editing.bin').read_bytes()==bytes(4), (name,'editor unexpectedly open',out)
        lcd=(out/f'{name}.lcd').read_bytes()
        lcd_view.png(lcd_view.screen(lcd),out/f'{name}.png',4)
        results[name]={'lcd_sha256':hashlib.sha256(lcd).hexdigest(),'scope':'native SETUP, EUCLID selected, editor closed'}
    for midi in (False,True):
        for page in (0,1):
            name=('midi' if midi else 'audio')+f'-page{page}'
            if selected and name not in selected: continue
            log=(out/f'{name}.log').read_text()
            assert 'ended on quit' in log and 'WAIT TIMEOUT' not in log, name
            bank=(out/f'{name}-bank.bin').read_bytes()[0]
            part=(out/f'{name}-part.bin').read_bytes()[0]
            actual=(out/f'{name}-settings.bin').read_bytes()
            offset=bank*3840+part*480+(240 if midi else 0)
            expected=bytes((9,4,1,4 if page else 0,0,48,1,1,65,0))
            assert actual[offset:offset+10]==expected, (name,actual[offset:offset+10].hex(),out)
            if page:
                for mirror in ('native-part','native-sram'):
                    native=(out/f'{name}-{mirror}.bin').read_bytes()
                    assert abs(int.from_bytes(native[0x3e8 if midi else 0x11a:][:1], 'big', signed=True))==64, (name,mirror,'RATE SPD')
                    assert native[0x500 if midi else 0x30a]==1, (name,mirror,'RATE MULT')
            assert (out/f'{name}-editing.bin').read_bytes()==b'\0\0\0\1', (name,'not editing',out)
            assert int.from_bytes((out/f'{name}-page.bin').read_bytes(),'big')==page, (name,'page',out)
            lcd=(out/f'{name}.lcd').read_bytes()
            lcd_view.png(lcd_view.screen(lcd),out/f'{name}.png',4)
            results[name]={'bank':bank,'part':part,'settings':expected.hex(),
                           'lcd_sha256':hashlib.sha256(lcd).hexdigest()}
    for midi in (False,True):
        name=('midi' if midi else 'audio')+'-burst'
        if selected and name not in selected: continue
        bank=(out/f'{name}-bank.bin').read_bytes()[0]
        part=(out/f'{name}-part.bin').read_bytes()[0]
        offset=bank*3840+part*480+(240 if midi else 0)
        actual=(out/f'{name}-settings.bin').read_bytes()[offset:offset+10]
        expected=bytes((4,1,0,0,0,48,0,0,64,0))
        assert actual==expected, (name,'fast/held counts accelerated or lost',actual.hex(),out)
        assert (out/f'{name}-editing.bin').read_bytes()==b'\0\0\0\1', (name,'editor closed',out)
        lcd=(out/f'{name}.lcd').read_bytes()
        lcd_view.png(lcd_view.screen(lcd),out/f'{name}.png',4)
        results[name]={'bank':bank,'part':part,'settings':actual.hex(),'interval_ms':15,
                       'lcd_sha256':hashlib.sha256(lcd).hexdigest()}
    for kind in ('audio','midi'):
        names=[f'{kind}-free-{duration}' for duration in ('short','long')]
        if selected and names[0] not in selected: continue
        phases=[]
        for name in names:
            log=(out/f'{name}.log').read_text()
            assert 'ended on quit' in log and 'WAIT TIMEOUT' not in log, name
            assert (out/f'{name}-editing.bin').read_bytes()==b'\0\0\0\1', (name,'not editing',out)
            state=(out/f'{name}-{kind}-state.bin').read_bytes()
            phases.append(int.from_bytes(state[:4],'big'))
        assert phases[0]!=phases[1], (kind,'FREE did not advance with transport stopped',phases,out)
        results[kind+'-free']={'phases':phases,'extra_stopped_ms':1700,
                               'input':'native WAVE/TRIG/SPD encoders, no PLAY or settings poke'}
    seed=bytearray(480)
    seed[:10]=bytes((9,4,1,4,0,48,1,1,65,0))
    seed[240:250]=bytes((10,4,1,4,0,48,1,1,65,0))
    for operation in part_cases:
        name='part-'+operation
        if selected and name not in selected: continue
        log=(out/f'{name}.log').read_text()
        assert 'ended on quit' in log and 'WAIT TIMEOUT' not in log, name
        bank=(out/f'{name}-bank.bin').read_bytes()[0]
        actual=(out/f'{name}-settings.bin').read_bytes()[bank*3840:(bank+1)*3840]
        expected=bytearray(3840); expected[:480]=seed
        if operation in ('save','reload'): expected[4*480:5*480]=seed
        if operation in ('paste','switch'): expected[480:960]=seed
        if operation=='switch': expected[480+240]=11
        # Always render the evidence, including failures, for menu diagnosis.
        lcd=(out/f'{name}.lcd').read_bytes()
        lcd_view.png(lcd_view.screen(lcd),out/f'{name}.png',4)
        assert actual==expected, (name,'Part state mismatch',out)
        part=(out/f'{name}-part.bin').read_bytes()[0]
        assert part==(1 if operation=='switch' else 0), (name,'linked Part',part,out)
        results[name]={'bank':bank,'part':part,'state_sha256':hashlib.sha256(actual).hexdigest(),
                       'lcd_sha256':hashlib.sha256(lcd).hexdigest()}
    receipt={'scope':'native UART panel WAVE/editor/controls/DIR and Part save/reload/paste/undo/clear/switch',
             'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),
             'panel_model':a.panel_model,
             'source_project':str(a.project.resolve()),'source_hashes':sources,'cases':results}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(f'PASS: native audio/MIDI panel controls and full LCD: {out / "receipt.json"}',flush=True)


if __name__=='__main__': main()
