#!/usr/bin/env python3
"""Render controlled Euclid LFO audio comparisons through native CF + DSP.

Generated fixture only; no device or source project is changed. Settings are
seeded before transport, not entered through the panel. Main output is the
port's documented ESAI slots 2/3. Keep raw captures and use one common preview
gain so accents and A/B differences cannot be hidden by per-clip normalization.
"""
import argparse
import hashlib
import json
import math
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import wave

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import toolpath  # noqa: E402,F401
from hw import ot_project as otp, ot_bank  # noqa: E402
from harness import stress_project  # noqa: E402
from verify_euclid_lfo_card import run  # noqa: E402

RATE = 44100
CASES = {
    '01-dry': dict(pulses=5, depth=0, volume=64),
    '02-zero-pulses': dict(pulses=0, depth=48, volume=0),
    '03-regular-4-in-16': dict(pulses=4, depth=48, volume=0),
    '04-euclid-5-in-16': dict(pulses=5, depth=48, volume=0),
    '05-euclid-5-in-16-accents': dict(pulses=5, depth=48, volume=0, accents=2),
    '06-filter-static': dict(pulses=5, depth=0, volume=64, filter=True),
    '07-filter-euclid': dict(pulses=5, depth=64, volume=64, filter=True),
}
SHOWCASE_CASES = {
    f'{i:02d}-7-steps-{pulses}-pulses-{accents}-accents':
    dict(steps=7, pulses=pulses, accents=accents, depth=48, volume=0, mult=1, boost=80)
    for i, (pulses, accents) in enumerate(((1, 0), (2, 0), (3, 0), (3, 2), (5, 2), (7, 3)), 1)
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(source, project):
    project.mkdir()
    hashes = {}
    for path in sorted(source.glob('*.work')):
        if path.name.startswith('eulf'): continue
        hashes[path.name] = digest(path)
        shutil.copy2(path, project / path.name)
    stress_project.set_project_text(project)
    stress_project.set_markers(project)
    sample = project / stress_project.SAMPLE_REL
    sample.parent.mkdir(parents=True)
    # Two-second seamless harmonic chord; half-Hz fundamentals and integer
    # harmonics complete whole cycles. No source-sample rhythm to confuse LFOs.
    pcm = bytearray()
    for n in range(stress_project.FRAMES):
        value = sum(math.sin(2 * math.pi * hz * h * n / RATE) / h
                    for hz in (110, 130.5, 164.5) for h in range(1, 13))
        v = round(value * 900)
        pcm.extend(struct.pack('<hh', v, v))
    with wave.open(str(sample), 'wb') as wav:
        wav.setparams((2, 2, RATE, 0, 'NONE', 'not compressed'))
        wav.writeframes(pcm)

    def populate(data):
        ot_bank.check_tags(data)
        for part in range(8):
            base = otp.PART_BASE + part * otp.PART_STRIDE
            for track in range(8):
                data[base + otp.MTYPE_OFF + track] = 1
                data[base + otp.FX1_OFF + track] = 4 if track == 0 else 0
                data[base + otp.FX2_OFF + track] = 0
                data[base + 0x2d3 + 5 * track + 1] = 0
                data[base + 0x1b + 2 * track] = 100 if track == 0 else 0
                data[base + 0x1e3 + 30 * track + 6] = 1
                data[base + 0x1e3 + 30 * track + 10] = 0
                data[base + 0x33 + 30 * track + 6] = 64
                data[base + 0x33 + 30 * track + 9] = 127
                p1 = base + otp.LFO_P1_OFF + 24 * track
                data[p1:p1 + 6] = bytes((64, 0, 0, 0, 0, 0))
                data[p1 + 6:p1 + 12] = bytes((0, 127, 127, 64, 64, 127))
                data[p1 + 12:p1 + 18] = bytes((0, 127, 0, 64, 0, 64))
                p2 = base + otp.LFO_PM_OFF + 30 * track
                data[p2:p2 + 6] = bytes((15, 0, 0, 19, 0, 0))
                data[p2 + 12:p2 + 18] = bytes((0, 0, 1, 0, 3, 0))
                data[base + 0x313 + 30 * track:base + 0x319 + 30 * track] = bytes(6)
        for pattern in range(16):
            data[ot_bank.PTRN_BASE + pattern * ot_bank.PTRN_STRIDE + ot_bank.PTRN_STRIDE - 5] = 0
            for track in range(8):
                off = otp.trac_off(pattern, track)
                data[off:off + 64] = bytes(64)
                data[off + 0x59:off + 0x59 + 64 * 32] = bytes([255]) * (64 * 32)
                if pattern == 0 and track == 0: data[off + 7] = 1
    otp._bank_write(project, 1, populate, guard=False)
    return hashes


def rms(values):
    return math.sqrt(sum(x * x for x in values) / max(1, len(values)))


def capture(out, name, frames):
    log = (out / (name + '.log')).read_text()
    assert 'DID NOT RETURN' not in log and 'ILLEGAL' not in log, name
    reached = re.search(r'frames run : (\d+).*target (\d+)\), run ended REACHED', log)
    assert reached and int(reached[1]) >= frames, name
    start = int(re.search(r'transport start at frame (\d+)', log)[1])
    with wave.open(str(out / (name + '_core0.wav')), 'rb') as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (8, 3, RATE)
        wav.setpos(start)
        raw = wav.readframes(frames * 16)
    stereo = [int.from_bytes(raw[i + ch * 3:i + ch * 3 + 3], 'little', signed=True)
              for i in range(0, len(raw), 24) for ch in (2, 3)]
    # Native frame counter and ESAI sink can finish within one block.
    assert len(stereo) >= (frames - 1) * 32, (name, 'short capture')
    return stereo


def showcase(out, inputs):
    """Native seven-step music, plus an explicitly post-mixed reference click."""
    cases = inputs['cases']
    duration = 8 * RATE  # Four bars; capture one extra block then trim exactly.
    preroll = round(inputs.get('preroll_seconds', 0) * RATE)
    samples, results = {}, {}
    for name, case in cases.items():
        raw = capture(out, name, inputs['frames'])
        assert len(raw) >= (preroll + duration) * 2
        assert max(map(abs, raw)) < 8388607, (name, 'raw clipping')
        samples[name] = raw[preroll * 2:(preroll + duration) * 2]
        mono = samples[name][::2]
        assert rms(mono) > 10, (name, 'silent')
        env = [rms(mono[i:i + 441]) for i in range(0, len(mono), 441)]
        starts = []
        for i, level in enumerate(env):
            # Ignore quiet ringing in a hit's tail, not just digital silence.
            if level > 1500 and (i == 0 or env[i - 1] <= 1500):
                # Group chord beating within one envelope, but keep every
                # 125 ms sixteenth distinct (including the dense 7/7 case).
                if not starts or i * .01 - starts[-1] > .09: starts.append(i * .01)
        steps = [s for s in range(7) if (s * case['pulses']) % 7 < case['pulses']]
        expected = [cycle * .875 + s * .125 for cycle in range(10) for s in steps
                    if cycle * .875 + s * .125 < 8]
        assert len(starts) == len(expected) and all(abs(x - y) <= .02 for x, y in zip(starts, expected)), (name, starts, expected)
        results[name] = dict(onsets_seconds=starts, pulses_per_cycle=case['pulses'],
                             accents_per_cycle=case['accents'], raw_sha256=digest(out / (name + '_core0.wav')))
    names = list(cases)
    # Matched 3/7 takes: accent pulse ordinals 0 and 2, no extra onsets.
    plain, accented = (samples[names[i]][::2] for i in (2, 3))
    ratios = []
    for i, onset in enumerate(results[names[2]]['onsets_seconds']):
        lo, hi = round(onset * RATE), round((onset + .09) * RATE)
        ratio = rms(accented[lo:hi]) / rms(plain[lo:hi])
        assert (ratio > 1.5 if i % 3 in (0, 2) else abs(ratio - 1) < .01), (i, ratio)
        ratios.append(ratio)
    gain = .55 * 8388607 / max(max(map(abs, v)) for v in samples.values())
    music = [0] * (2 * RATE * 2)  # One-bar count-in.
    timeline = []
    for index, (name, values) in enumerate(samples.items()):
        timeline.append(dict(start_seconds=2 + index * 8, duration_seconds=8, **cases[name]))
        for i, value in enumerate(values):
            edge = min(1, (i // 2) / 220, (duration - 1 - i // 2) / 220)
            music.append(round(value * gain * edge))
    click = [0] * len(music)
    beat_samples = RATE // 2
    for beat in range(len(music) // 2 // beat_samples):
        hz = 2400 if beat % 4 == 0 else 1700
        for n in range(660):
            v = round(.12 * 8388607 * math.sin(2 * math.pi * hz * n / RATE)
                      * math.exp(-n / 100) * min(1, n / 8))
            pos = 2 * (beat * beat_samples + n)
            click[pos] = click[pos + 1] = v
    outputs=[('seven-sixteenths-with-click.wav', [a + b for a, b in zip(music, click)]),
             ('seven-sixteenths-music-only.wav', music), ('reference-click.wav', click)]
    for index,name in enumerate(samples):
        start=(2+index*8)*RATE*2
        outputs.append((name+'-with-click.wav', [a+b for a,b in zip(music[start:start+duration*2],click[:duration*2])]))
    for filename, values in outputs:
        assert max(map(abs, values)) < 8388607, (filename, 'mix clipping')
        with wave.open(str(out / filename), 'wb') as wav:
            wav.setparams((2, 3, RATE, 0, 'NONE', 'not compressed'))
            wav.writeframes(b''.join(v.to_bytes(3, 'little', signed=True) for v in values))
    receipt = dict(image_sha256=digest(out / 'mainos.bin'), input=inputs, results=results,
                   bpm=120, step_division='1/16', step_seconds=.125, cycle_seconds=.875, steps_per_cycle=7, timeline=timeline,
                   discarded_native_preroll_seconds=preroll / RATE, onset_rms_threshold=1500,
                   common_music_gain=gain, matched_accent_hit_rms_ratios=ratios,
                   duration_seconds=len(music) / (2 * RATE),
                   preview_sha256={name:digest(out/name) for name,_ in outputs},
                   click='Post-mixed quarter-note reference at 120 BPM; brighter click on each downbeat.',
                   limits='Music is native-emulator output; reference click and montage are presentation only, not hardware evidence.')
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(f'PASS: seven-step showcase, onset/accent/no-clipping checks: {out}', flush=True)


def analyze(out):
    inputs = json.loads((out / 'inputs.json').read_text())
    if inputs.get('showcase'): showcase(out, inputs); return
    samples, results = {}, {}
    for name in CASES:
        stereo = capture(out, name, inputs['frames'])
        samples[name] = stereo
        peak = max(map(abs, stereo))
        results[name] = dict(duration_seconds=len(stereo) / (2 * RATE),
                             peak_dbfs=20 * math.log10(max(1, peak) / 8388608),
                             rms=rms(stereo), clipped_samples=sum(abs(x) >= 8388607 for x in stereo),
                             raw_sha256=digest(out / (name + '_core0.wav')))
        assert results[name]['clipped_samples'] == 0, (name, 'clipping')
    silent = results['02-zero-pulses']['rms']
    assert silent == 0, ('zero pulses must produce digital silence', silent)
    for name in CASES:
        if name != '02-zero-pulses': assert results[name]['rms'] > max(10, silent * 10), (name, 'silent')
    comparisons = {}
    for before, after in [('03-regular-4-in-16', '04-euclid-5-in-16'),
                          ('04-euclid-5-in-16', '05-euclid-5-in-16-accents'),
                          ('06-filter-static', '07-filter-euclid')]:
        a, b = samples[before], samples[after]
        delta = rms([x - y for x, y in zip(a, b)]) / max(1, rms(a))
        assert delta > 0.1, (before, after, 'no meaningful output change', delta)
        comparisons[after] = dict(reference=before, residual_relative_rms=delta)
    assert results['05-euclid-5-in-16-accents']['rms'] > results['04-euclid-5-in-16']['rms'] * 1.1
    # Independent audible-output oracle: 64 SPD / 1x / 120 BPM gives a
    # four-second cycle. Expected Euclidean hits are steps 0,4,7,10,13.
    # Detect in 10 ms RMS windows, grouping within one envelope attack/tail.
    onsets = {}
    for name in ('03-regular-4-in-16', '04-euclid-5-in-16', '05-euclid-5-in-16-accents'):
        mono = samples[name][::2]
        envelope = [rms(mono[i:i + 441]) for i in range(0, len(mono), 441)]
        starts = []
        for i, value in enumerate(envelope):
            if value > 200 and (i == 0 or envelope[i - 1] <= 200):
                if not starts or i * .01 - starts[-1] > .2: starts.append(i * .01)
        steps = (0, 4, 8, 12) if name.startswith('03') else (0, 4, 7, 10, 13)
        expected = [cycle * 4 + step * .25 for cycle in range(math.ceil(len(mono) / RATE / 4))
                    for step in steps if cycle * 4 + step * .25 < len(mono) / RATE - .02]
        assert len(starts) == len(expected) and all(abs(a - b) <= .02 for a, b in zip(starts, expected)), (name, starts, expected)
        onsets[name] = starts
    ratios = []
    plain, accented = (samples[name][::2] for name in ('04-euclid-5-in-16', '05-euclid-5-in-16-accents'))
    for i, t in enumerate(onsets['04-euclid-5-in-16']):
        lo, hi = round(t * RATE), round((t + .2) * RATE)
        ratio = rms(accented[lo:hi]) / rms(plain[lo:hi])
        # Two accents over five pulses are ordinals 0 and 3, not extra hits.
        assert (ratio > 1.5 if i % 5 in (0, 3) else abs(ratio - 1) < .01), (i, ratio)
        ratios.append(ratio)
    gain = 0.7 * 8388607 / max(max(map(abs, x)) for x in samples.values())
    for name, values in samples.items():
        preview = bytearray()
        for i, value in enumerate(values):
            # Only 5 ms at file edges; never reshape the actual rhythmic hits.
            edge = min(1, (i // 2) / 220, (len(values) // 2 - 1 - i // 2) / 220)
            preview.extend(round(value * gain * edge).to_bytes(3, 'little', signed=True))
        with wave.open(str(out / (name + '.wav')), 'wb') as wav:
            wav.setparams((2, 3, RATE, 0, 'NONE', 'not compressed'))
            wav.writeframes(preview)
    receipt = dict(image_sha256=digest(out / 'mainos.bin'), input=inputs,
                   results=results, comparisons=comparisons, common_preview_gain=gain,
                   audible_onsets_seconds=onsets, accented_to_plain_hit_rms=ratios,
                   limits='Native emulator audio, not physical hardware or external MIDI audio; seeded settings, not panel entry.')
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2), flush=True)
    print(f'PASS: audible Euclid LFO comparisons: {out}', flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project', type=pathlib.Path)
    ap.add_argument('--analyze', type=pathlib.Path)
    ap.add_argument('--seconds', type=float, default=8)
    ap.add_argument('--showcase', action='store_true', help='seven-step variations, four bars each, with quarter-note reference click')
    a = ap.parse_args()
    if a.analyze: analyze(a.analyze); return
    if a.project is None or not (a.project / 'bank01.work').is_file(): ap.error('--project needs a fixture project')
    if a.seconds < 8: ap.error('at least eight seconds required for rhythm comparisons')
    if a.showcase and a.seconds != 8: ap.error('--showcase uses exactly eight seconds per variation')
    parent = ROOT / 'out/euclid-lfo-audio'; parent.mkdir(exist_ok=True)
    out = pathlib.Path(tempfile.mkdtemp(prefix='audio-', dir=parent))
    print(f'Native audio comparisons: {out}', flush=True)
    sources = fixture(a.project, out / 'project')
    run(['make', 'bus', 'REMIX=euclid-lfo'], out / 'build.log')
    shutil.copy2(ROOT / 'out/mainos_bus.bin', out / 'mainos.bin')
    nm = subprocess.check_output(['m68k-elf-nm', str(ROOT / 'out/platform/runtime/runtime.elf')], text=True)
    symbols = {s[2]: int(s[0], 16) for line in nm.splitlines() if len(s := line.split()) == 3}
    preroll = 1.75 if a.showcase else 0  # Two complete seven-sixteenth cycles.
    frames = math.ceil((a.seconds + preroll) * RATE / 16) + int(a.showcase)
    cases = SHOWCASE_CASES if a.showcase else CASES
    (out / 'inputs.json').write_text(json.dumps(dict(frames=frames, cases=cases, showcase=a.showcase, preroll_seconds=preroll, source_hashes=sources), indent=2) + '\n')
    run([ROOT / '.venv/bin/python3', 'tools/emu/ot_emu/stage_card.py', out / 'project', 'EUCLID', 'LFO',
         '--tree', out / 'tree', '--out', out / 'input.img',
         '--audio', f'{out / "project" / stress_project.SAMPLE_REL}:LFO/{stress_project.SAMPLE_REL}'], out / 'stage.log')
    command = [ROOT / 'out/emu/ot_emu', '--image', out / 'mainos.bin', '--card', out / 'input.img',
               '--dsp', '--set', 'EUCLID', '--project', 'LFO', '--load-ms', '90000',
               '--main-level', '64', '--audio-out', out / 'boot']
    for name, case in cases.items():
        params = (case.get('steps', 16), case['pulses'], 0, 0, 8, 72 if case.get('filter') else 48,
                  case.get('accents', 0), 0, case.get('boost', 127), 0)
        edits = [f'{symbols["eul_bank"] + i:#x}={value}' for i, value in enumerate(params)]
        base = 0x400e21e0 + 0x8ed80
        edits += [f'{base + offset:#x}={value}' for offset, value in (
            (0x11d, case['depth']), (0x123, case['volume']),
            (0x2f2, 19 if case.get('filter') else 15),
            (0x127, 24 if case.get('filter') else 127), (0x30a, case.get('mult', 0)))]
        command += ['--scenario', f'{out / (name + ".log")} --sequencer --internal-clock --frames {frames} '
                    f'--step -:poke:{";".join(edits)} --step -:call:0x40009094,0,0 --audio-out {out / name}']
    run(command, out / 'boot.log')
    assert all(digest(a.project / name) == value for name, value in sources.items()), 'source project changed'
    analyze(out)


if __name__ == '__main__': main()
