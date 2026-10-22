#!/usr/bin/env python3
"""Linked formatter, context, bounds and write-isolation checks on this image."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess

import midi_scales_machine as harness
from unicorn import m68k_const as registers

ROOT = Path(__file__).resolve().parents[2]


def symbols():
    rows = subprocess.check_output(['m68k-elf-nm', str(ROOT/'out/platform/runtime/runtime.elf')], text=True)
    return {parts[2]: int(parts[0], 16) for line in rows.splitlines()
            if len(parts := line.split()) == 3 and parts[2].startswith('mu_')}


def expected_beats(value, tempo24=2880):
    # Musical definitions, independent of the firmware's table/rounding code.
    for denominator in (1, 2, 4, 8, 16, 32, 64, 128):
        for suffix, factor in (('', Fraction(1)), ('.', Fraction(3, 2)), ('T', Fraction(2, 3))):
            text = f'1/{denominator}{suffix}'
            if len(text) <= 5 and value == Fraction(4, denominator) * factor:
                return text
    return expected_ms(round_half(value * 1440000 / tempo24))


def round_half(value):
    return (2*value.numerator + value.denominator)//(2*value.denominator)


def expected_ms(ms):
    if ms < 1000:
        return f'{ms}ms'
    centi = (ms+5)//10
    if centi < 1000:
        return f'{centi//100}.{centi%100:02d}s'
    deci = (ms+50)//100
    if deci < 1000:
        return f'{deci//10}.{deci%10}s'
    return f'{(ms+500)//1000}s'


class Machine(harness.Machine):
    def __init__(self):
        super().__init__(symbol_loader=symbols)
        self.bank = 0x400e0000
        self.uc.mem_write(0x46c82456, self.bank.to_bytes(4, 'big'))
        self.calls = 0
        self.labels = set()
        self.uc.mem_write(0x8000181c, (2880).to_bytes(4, "big"))

    def fmt(self, name, raw, *, rational=None):
        u = self.uc
        u.mem_write(self.scratch-1, b'\xa5' + b'?'*6 + b'\xa5')
        u.mem_write(self.stack+4, self.scratch.to_bytes(4, 'big') + raw.to_bytes(4, 'big', signed=True))
        keep = {getattr(registers, 'UC_M68K_REG_'+name): 0x12340000+i
                for i, name in enumerate(('D2','D3','D4','D5','D6','D7','A2','A3','A4','A5','A6'))}
        args = {} if rational is None else dict(d0=rational[0], d1=rational[1], a0=self.scratch)
        self.call(name, regs=keep, **args)
        self.calls += 1
        assert all(u.reg_read(reg) == value for reg, value in keep.items()), name
        assert bytes(u.mem_read(self.scratch-1, 1)) == bytes(u.mem_read(self.scratch+6, 1)) == b'\xa5', name
        data = bytes(u.mem_read(self.scratch, 6))
        assert b'\0' in data, (name, raw, data)
        for at, length in self.writes:
            assert (self.scratch <= at < at+length <= self.scratch+6 or
                    self.stack-2048 <= at < at+length <= self.stack+12), (name, hex(at), length)
        label = data.split(b'\0')[0].decode('ascii')
        self.labels.add(label)
        return label

    def context(self, midi, track, part, lfo, mult):
        u = self.uc
        u.mem_write(0x100b14cc, bytes([track]))
        u.mem_write(0x100b14cf, bytes([part]))
        u.mem_write(0x460d1a32, lfo.to_bytes(4, 'big'))
        at = self.bank + part*6322 + track*(36 if midi else 30) + (0x8f280 if midi else 0x8f08a) + lfo
        u.mem_write(at, bytes([mult]))


def verify_descriptor_controls(selection, remix_argument):
    """The menu gate accepts declared adapters and rejects pointer/data damage."""
    if 'DELAY' not in selection.modules:
        return
    import contextlib
    import io
    import os
    import tempfile
    from unittest.mock import patch
    with patch.dict(os.environ, REMIX=remix_argument):
        import verify_menu
    original = (ROOT/'out/mainos_bus.bin').read_bytes()
    for label, address in (('declared', None), ('wrong formatter', 0x400d4b98),
                           ('unrelated default', 0x400d4ace+0x6a)):
        with tempfile.TemporaryDirectory(prefix='musical_units_menu_') as temp:
            data = bytearray(original)
            if address is not None:
                data[address-0x40000400] ^= 1
            path = Path(temp)/'image.bin'
            path.write_bytes(data)
            path.with_suffix('.remix').write_text(selection.name+' '+hashlib.sha256(data).hexdigest())
            output = io.StringIO()
            status = 0
            with patch.object(verify_menu, 'BUILT', path), contextlib.redirect_stdout(output):
                try:
                    verify_menu.main()
                except SystemExit as exc:
                    status = exc.code
            assert (status == 0) == (address is None), (label, output.getvalue())
    print('  [ok] menu gate accepts declared adapters; rejects wrong pointer and unrelated default changes')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('remix', nargs='?', default='musical-units')
    args = ap.parse_args()
    from remix import registry
    selection = registry.remix(args.remix)
    verify_descriptor_controls(selection, args.remix)
    m = Machine()
    for mode, base in (('audio', 0x400d37be), ('midi', 0x400d412a)):
        for slot, name in ((0, 'one'), (1, 'two'), (2, 'three'), (10, 'setup')):
            assert int.from_bytes(m.uc.mem_read(base+0x102+slot*4, 4), 'big') == m.sym[f'mu_{mode}_{name}']
    # Additional adapters keep the original numeric/dial widget style.
    adapters = ((0x400d3e06,2,'mu_note_length','mu_bar_widget'),
                (0x400d3f98,5,'mu_note_length','mu_widget'),
                (0x400d3f98,3,'mu_arp_speed','mu_bar_widget'),
                (0x400d3f98,0,'mu_transpose','mu_widget'),
                (0x400d3c74,6,'mu_record_fade','mu_widget'),
                (0x400d3c74,7,'mu_record_fade','mu_widget'),
                (0x400d2fe4,5,'mu_retrig','mu_widget'),
                (0x400d3176,5,'mu_retrig','mu_widget'))
    for base,slot,formatter,widget in adapters:
        for offset,symbol in ((0x102,formatter),(0x132,widget)):
            assert int.from_bytes(m.uc.mem_read(base+offset+slot*4,4),'big') == m.sym[symbol]
    # Stock DELAY is registered through the existing cross-module mechanism.
    delay_formatter = m.sym['mu_delay'] if 'DELAY' in selection.modules else 0x4003c718
    assert int.from_bytes(m.uc.mem_read(0x400d4a96+0x102, 4), 'big') == delay_formatter
    for base, slots in ((0x400d37be,(0,1,2,10)),(0x400d412a,(0,1,2,10)),(0x400d4a96,(0,))):
        for slot in slots:
            assert int.from_bytes(m.uc.mem_read(base+0x132+slot*4,4),'big')==m.sym['mu_widget']
    print('  [ok] all eight LFO formatter pointers and stock DELAY registration installed')

    for mode in ('audio', 'midi'):
        for lfo, name in enumerate(('one', 'two', 'three')):
            for mult in range(7):
                m.context(mode == 'midi', 0, 0, lfo, mult)
                results = []
                for speed in range(128):
                    want = expected_beats(Fraction(512, speed*(1 << mult))) if speed else 'STOP'
                    got = m.fmt(f'mu_{mode}_{name}', speed)
                    assert got == want, (mode, name, speed, mult, got, want)
                    results.append(got)
    print('  [ok] audio/MIDI x three LFOs x seven MULT x 128 SPD; ms/s between divisions; exact divisions never approximate')

    for midi in (False, True):
        mode = 'midi' if midi else 'audio'
        for track in range(8):
            for part in range(4):
                for lfo, name in enumerate(('one', 'two', 'three')):
                    mult = (track+part+lfo) % 7
                    m.context(midi, track, part, lfo, mult)
                    for speed in (0, 1, 32, 63, 96, 127):
                        assert m.fmt(f'mu_{mode}_setup', speed) == m.fmt(f'mu_{mode}_{name}', speed)
    print('  [ok] SETUP/main agreement across every track, Part and LFO, including intermediate values')

    for track in range(8):
        for part in range(4):
            m.context(False, track, part, 0, 0)
            sync = m.bank + part*6322 + track*30 + 0x8f087
            for on in (False, True):
                m.uc.mem_write(sync, bytes([on]))
                for raw in range(128):
                    want = expected_beats(Fraction(raw+1, 32)) if on else str(raw+1)
                    assert m.fmt('mu_delay', raw) == want, (track, part, on, raw, want)
    print('  [ok] DELAY all 128 values x eight tracks x four Parts; SYNC OFF retains native numbers')

    # Independent musical definitions and the actual engine's read-only ladder.
    # Recorder ladder: 0, 1..32, then 16 values per octave of step size.
    ladder = list(range(33))
    for power in range(1,6):
        ladder.extend(range(17*(1<<power),33*(1<<power),1<<power))
    assert len(ladder) == 113
    for raw,value in enumerate(ladder):
        native=int.from_bytes(m.uc.mem_read(0x400ab63a+raw*4,4),'big')
        assert native == value*992250, (raw,native,value)
    for tempo in (720,721,2879,2880,3600,7200):
        m.uc.mem_write(0x8000181c,tempo.to_bytes(4,'big'))
        for raw in range(128):
            want = 'INF' if raw==127 else ('0' if raw==0 else expected_beats(Fraction(raw,24),tempo))
            assert m.fmt('mu_note_length',raw)==want, ('LEN',tempo,raw,want)
            assert m.fmt('mu_transpose',raw)==f'{raw-64}st'
            if raw<96:
                assert m.fmt('mu_arp_speed',raw)==expected_beats(Fraction(raw+1,24),tempo)
            if raw<113:
                assert m.fmt('mu_record_fade',raw)==expected_beats(Fraction(ladder[raw],64),tempo)
            native=int.from_bytes(m.uc.mem_read(0x400aae0c+raw*16,4),'big')
            nominal=2**((raw-91)/12)/4
            assert abs(native - nominal*1016064000)<1, (raw,native,nominal)
            if raw>=7 and (raw-7)%12==0:
                want=expected_beats(Fraction(1<<((raw-7)//12),512),tempo)
            else:
                want=expected_ms(round_half(Fraction(native*10,7056*tempo)))
            assert m.fmt('mu_retrig',raw)==want, ('RTIM',tempo,raw,want)
    for name,limit in (('mu_note_length',128),('mu_arp_speed',96),('mu_transpose',128),
                       ('mu_record_fade',113),('mu_retrig',128)):
        for raw in (-1,limit,100000):
            assert m.fmt(name,raw)=='?', (name,raw)
    print('  [ok] MIDI LEN/NLEN, ARP SPD/TRAN, recorder fades, STATIC/FLEX RTIM: all values at six tempos')
    m.uc.mem_write(0x8000181c,(2880).to_bytes(4,'big'))

    # Execute the stock note-off counter assignment, including the high end.
    # The native display table has odd fractions there; the engine stays raw*4.
    m.sym['stock_note_counter']=0x4009fd58
    for raw in range(128):
        frame=m.scratch+512; counter=m.scratch+1024
        m.uc.mem_write(frame-20,counter.to_bytes(4,'big'))
        m.call('stock_note_counter',d0=raw,regs={registers.UC_M68K_REG_A6:frame},stop=0x4009fd6e)
        assert int.from_bytes(m.uc.mem_read(counter,4),'big') == (0 if raw==127 else raw*4)
    print('  [ok] stock MIDI length counter: all 128 raw values, including zero and infinity')
    # RTIM advances by tempo24 * 16 per rendered sample, not tempo24.
    # Pin that factor by executing the stock counter-rate publisher.
    m.sym['stock_retrig_rate']=0x4000405e
    for tempo in (720,2880,7200):
        m.uc.mem_write(0x8000181c,tempo.to_bytes(4,'big'))
        m.call('stock_retrig_rate',regs={registers.UC_M68K_REG_A3:m.scratch},stop=0x4000406a)
        assert int.from_bytes(m.uc.mem_read(m.scratch+28,4),'big') == tempo*16
    m.uc.mem_write(0x8000181c,(2880).to_bytes(4,'big'))
    print('  [ok] stock RTIM counter rate: 16 * tempo24 per sample')

    # Public helper integration: rational durations from another module,
    # exact dotted/triplet names and carry boundaries within six-byte buffers.
    for n, d in ((1, 4), (3, 8), (1, 6), (1, 32), (4, 1), (6, 1), (8, 1),
                 (127, 1000), (1999, 2000), (1999, 200), (1999, 20), (1999, 2)):
        assert m.fmt('mu_beats', 0, rational=(n, d)) == expected_beats(Fraction(n, d)), (n, d)
    assert m.fmt('mu_beats', 0, rational=(1, 0)) == '?'
    for tempo in (720, 721, 2879, 2880, 3600, 7200):
        m.uc.mem_write(0x8000181c, tempo.to_bytes(4, 'big'))
        for speed in range(1, 128):
            m.context(False, 0, 0, 0, 6)
            assert m.fmt('mu_audio_one', speed) == expected_beats(Fraction(512, speed*64), tempo)
        m.uc.mem_write(m.bank+0x8f087, b'\x01')
        for raw in range(128):
            value = Fraction(raw+1, 32)
            want = '4s' if value*1440/tempo > 4 else expected_beats(value, tempo)
            assert m.fmt('mu_delay', raw) == want, (tempo, raw, want)
    print('  [ok] tempo-dependent milliseconds/seconds at six tempos; synced delay four-second cap')
    for ms in (0, 1, 60, 123, 999, 1000, 2540, 9994, 9995, 99949, 99950, 9999000):
        assert m.fmt('mu_milliseconds', 0, rational=(ms, 1)) == expected_ms(ms)

    print('  [ok] reusable rational formatter, musical notation and decimal carry boundaries')
    m.sym['native_width'] = 0x40012f30
    for label in m.labels:
        m.uc.mem_write(m.scratch, label.encode()+b'\0')
        m.uc.mem_write(m.stack+4, b''.join(n.to_bytes(4, 'big') for n in
                                        (0x400ba876, 0xffffffff, m.scratch)))
        assert m.call('native_width') <= 19, label
    print(f'  [ok] {len(m.labels)} distinct labels fit the native 19-pixel text area')
    print(f'  [ok] {m.calls} formatter calls: <=5 characters, guarded buffers, preserved ABI, no state writes')
    result = {'status': 'pass', 'formatter_calls': m.calls,
              'image_sha256': hashlib.sha256((ROOT/'out/mainos_bus.bin').read_bytes()).hexdigest(),
              'scope': 'linked formatters and installed descriptors; engine and live panel checked separately'}
    out = ROOT/'out/musical-units'; out.mkdir(exist_ok=True)
    (out/'formatters.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
