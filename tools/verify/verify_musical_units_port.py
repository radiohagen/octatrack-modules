#!/usr/bin/env python3
"""Measure stock audio/MIDI LFO timing on a disposable native-port project.

Run after capture_manual.py musical-units. The card must be a disposable
fixture: the port opens it writable, as MenuPort normally does.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import toolpath
from stems_panel import MenuPort


def verify(p):
    # The sequencer runs MIDI LFOs at 96 updates per quarter note at normal
    # tempo. Observe the real call site; do not infer that from audio frames.
    p.press('play');p.run(100)
    p.proc.command('watch 0x40003df8', 'ok');p.run(1000)
    hits=p.proc.command('hits', 'hits')
    entries=[row.split(':') for row in hits.split() if ':40003df8:' in row]
    assert len(entries)==192, len(entries)  # fixture tempo = 120 BPM
    assert all(int(row[8],16)==0 for row in entries), 'unexpected coarse MIDI tick'
    p.proc.command('watch off', 'ok');p.press('stop');p.rt.frame=False
    p.poke(0x800000e0, bytes(4))
    p.poke(0x80004858, bytes(64))
    audio=[]
    for bpm, speed, mult in ((30,32,0),(90,63,3),(120,64,6),(120,96,5),(300,127,6)):
        p.poke(0x8000181c, (bpm*24).to_bytes(4,'big'))
        p.poke(0x800010e8, bytes(24*28))
        p.poke(0x80000510, bytes(8*48))
        p.poke(0x8000051c, (speed*256).to_bytes(2,'big'))
        p.poke(0x80000534, bytes([mult]))
        for _ in range(16):p.proc.command('call 0x40003b90', 'ok')
        actual=p.long(0x800010e8)
        expected=16*16/44100 * bpm/60 * speed*(1<<mult)/512 * (1<<23)
        # Stock fixed-point reciprocal and per-frame integer quantization.
        assert abs(actual-expected) <= max(16*(1<<mult), expected*.005), (bpm,speed,mult,actual,expected)
        audio.append(dict(bpm=bpm,speed=speed,mult=1<<mult,phase=actual,nominal_phase=expected))
    midi=[]
    for speed,mult in ((1,0),(32,3),(63,6),(64,6),(96,5),(127,6)):
        p.poke(0x46c770e0, bytes(24*28))
        p.poke(0x46c76fe0, bytes(8*32))
        p.poke(0x46c76dc0, bytes(8*68))
        p.poke(0x46c76fe6, bytes([speed]))
        p.poke(0x46c76dfe, bytes([mult]))
        for _ in range(3):p.proc.command('call 0x40003df8 0', 'ok')
        actual=p.long(0x46c770e0)
        expected=speed*512*(1<<mult)
        assert abs(actual-expected) <= 3*(1<<mult), (speed,mult,actual,expected)
        midi.append(dict(speed=speed,mult=1<<mult,phase=actual))
    return dict(midi_ticks_per_second_at_120_bpm=len(entries),audio=audio,midi=midi)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--capture',type=Path,default=ROOT/'out/manual-captures/musical-units')
    args=ap.parse_args();work=args.capture
    with MenuPort(work/'image.bin',work/'card.img','MANUAL','SCREENS',True,log_path=work/'timing-port.log') as p:
        p.settle()
        assert p.long(0x8000181c)==2880, 'timing fixture must start at 120 BPM'
        result=verify(p)
    result.update(status='pass',image_sha256=hashlib.sha256((work/'image.bin').read_bytes()).hexdigest(),
                  scope='native emulator; nominal full-cycle periods, not hardware acceptance')
    (work/'timing.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: audio phase at five settings; MIDI at six settings; 96 MIDI updates per beat')


if __name__=='__main__':main()
