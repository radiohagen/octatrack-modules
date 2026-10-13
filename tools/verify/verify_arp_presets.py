#!/usr/bin/env python3
"""Exercise the built ARP PRESETS code and native editor in ColdFire Unicorn.

All presets, all Parts/tracks, first/last bank, exact write boundaries, CS1,
live length, interrupt state, custom recognition, native C/F/LEVEL/rotation
and title selection. Display/LED calls are stubbed here; the port UI capture
is separate. This is not physical MIDI or hardware validation.
"""
import argparse
import pathlib
import struct
import subprocess
import sys
from fractions import Fraction

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import toolpath  # noqa: E402,F401
import emu_bringup  # noqa: E402,F401  selects the patched Unicorn
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE  # noqa: E402
from unicorn import m68k_const as K  # noqa: E402
from remix import registry, booted  # noqa: E402

# Independent musical oracle: one-based active steps, not firmware masks.
PATTERNS = [
    ('STRAIGHT', 16, list(range(1, 17))),
    ('EIGHTHS', 16, list(range(1, 17, 2))),
    ('OFFBEAT', 16, [3, 7, 11, 15]),
    ('PULSE4', 16, [1, 5, 9, 13]),
    ('TRESILLO', 8, [1, 4, 7]),
    ('CINQUIL', 8, [1, 3, 4, 6, 7]),
    ('SON3-2', 16, [1, 4, 7, 11, 13]),
    ('SON2-3', 16, [3, 5, 9, 12, 15]),
    ('E5/16', 16, [1, 4, 7, 10, 13]),
    ('E7/16', 16, [1, 4, 6, 8, 11, 13, 15]),
    ('E3/7', 7, [1, 3, 5]),
    ('E2/5', 5, [1, 3]),
    ('E4/9', 9, [1, 3, 5, 7]),
    ('E5/12', 12, [1, 3, 5, 8, 10]),
    ('OCTPULSE', 8, [1, 3, 5, 7]),
    ('OCT332', 8, [1, 4, 7]),
    ('KENTBASS', 16, [2, 4, 7, 11, 14, 16]),
]
DB, STRIDE = 0x400e21e0, 0x9b340
STOP, STACK = 0x10000, 0x30000


class Machine:
    def __init__(self):
        self.uc = u = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        u.ctl_set_cpu_model(K.UC_CPU_M68K_CFV4E)
        for a, n in ((0x40000000, 0x8000000), (0x10000000, 0x100000),
                     (0x80000000, 0x100000), (STOP, STACK)):
            u.mem_map(a, n)
        u.mem_write(0x40000400, booted.image((ROOT / 'out/mainos_bus.bin').read_bytes(), ROOT / 'out/platform'))
        nm = subprocess.check_output(['m68k-elf-nm', '--extern-only', '--defined-only', str(ROOT / 'out/platform/runtime/runtime.elf')], text=True)
        # Local assembly labels can share names with exported C routines.
        # Resolve the ARP ABI only from external symbols (PLOCKS also has ap_apply).
        self.symbols = {p[2]: int(p[0], 16) for p in map(str.split, nm.splitlines()) if len(p) == 3}
        self.title = None
        for a in (0x40079d48, 0x4007e998, 0x400570b8):
            u.hook_add(UC_HOOK_CODE, self.stub, begin=a, end=a)

    def stub(self, u, address, size, user):
        sp = u.reg_read(K.UC_M68K_REG_A7)
        if address == 0x400570b8:
            title = self.r32(sp + 8)
            self.title = self.read(title, 32).split(b'\0')[0].decode()
        u.reg_write(K.UC_M68K_REG_PC, self.r32(sp))
        u.reg_write(K.UC_M68K_REG_A7, sp + 4)

    def read(self, a, n): return bytes(self.uc.mem_read(a, n))
    def write(self, a, data): self.uc.mem_write(a, bytes(data))
    def w32(self, a, v): self.write(a, struct.pack('>I', v & 0xffffffff))
    def r32(self, a): return int.from_bytes(self.read(a, 4), 'big')

    def call(self, name, *args):
        u = self.uc
        addr = self.symbols[name] if isinstance(name, str) else name
        saved = [getattr(K, f'UC_M68K_REG_{r}{i}') for r, ns in (('D', range(2, 8)), ('A', range(2, 7))) for i in ns]
        for i, reg in enumerate(saved): u.reg_write(reg, 0x12340000 + i)
        u.reg_write(K.UC_M68K_REG_SR, 0x2300)
        u.reg_write(K.UC_M68K_REG_A7, STACK)
        self.write(STACK, struct.pack('>' + 'I' * (len(args) + 1), STOP, *(v & 0xffffffff for v in args)))
        u.emu_start(addr, STOP, count=100000)
        assert u.reg_read(K.UC_M68K_REG_PC) == STOP, (name, hex(u.reg_read(K.UC_M68K_REG_PC)))
        assert u.reg_read(K.UC_M68K_REG_A7) == STACK + 4, name
        assert u.reg_read(K.UC_M68K_REG_SR) & 0x2700 == 0x2300, 'interrupt mask leaked'
        assert all(u.reg_read(reg) == 0x12340000 + i for i, reg in enumerate(saved)), 'callee-saved register changed'
        return u.reg_read(K.UC_M68K_REG_D0)

    def seed(self, bank=0, part=0, track=0):
        self.bank, self.part, self.track = DB + bank * STRIDE, part, track
        self.write(self.bank, b'\xa5' * STRIDE)
        self.write(0x100a0000, b'\x5a' * 0x10000)
        self.write(0x46c76dc0, b'\x3c' * (68 * 8))
        self.w32(0x46c82456, self.bank)
        self.write(0x100b14cf, [part]); self.write(0x100b14cc, [track])
        self.write(0x100b145e, [0x80]); self.w32(0x100f8598, 0)
        self.write(0x460e73a0, b'\0\0')

    def state(self):
        return (self.read(self.bank, STRIDE), self.read(0x100a0000, 0x10000), self.read(0x46c76dc0, 544))

    def expected(self, before, index):
        bank, shadow, live = map(bytearray, before)
        _, length, steps = PATTERNS[index]
        mask = sum(1 << (s - 1) for s in steps).to_bytes(2, 'big')
        offsets = bytearray(16)
        if index == 14: offsets[4] = offsets[6] = 12
        if index == 15: offsets[6] = 12
        p, t = self.part * 0x18b2, self.track
        for data, o, m, l in ((bank, 0x905b2, 0x905a2, 0x8f270),
                             (shadow, 0x6700, 0x66f0, 0x53be)):
            data[p + o + t * 16:p + o + t * 16 + 16] = offsets
            data[p + m + t * 2:p + m + t * 2 + 2] = mask
            data[p + l + t * 36] = length - 1
        bank[0x95048] |= 1 << self.part
        bank[0x9b332:0x9b336] = b'\0\0\0\1'
        live[68 * t + 46] = length - 1
        return tuple(map(bytes, (bank, shadow, live)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('remix', nargs='?', default='arp-presets')
    a = ap.parse_args()
    if 'ARP PRESETS' not in registry.remix(a.remix).modules:
        print('  [ -- ] no ARP PRESETS'); return
    subprocess.run([sys.executable, str(ROOT / 'modules/arp-presets/generate.py'), '--check'], check=True)
    for name, n, steps in PATTERNS:
        if name.startswith('E') and '/' in name:
            hits = {s - 1 for s in steps}
            for width in range(1, n):
                counts = [sum((s + j) % n in hits for j in range(width)) for s in range(n)]
                assert max(counts) - min(counts) <= 1, (name, width, counts)
    m = Machine()
    # Derive labels from musical durations, independently of the C switch.
    divisions = {}
    for denominator in (1, 2, 4, 8, 16, 32, 64):
        for ratio, label in ((Fraction(1), f'1/{denominator}'),
                             (Fraction(2, 3), f'{denominator}T'),
                             (Fraction(3, 2), f'{denominator}D')):
            ticks = Fraction(96, denominator) * ratio
            if ticks.denominator == 1 and 1 <= ticks <= 96:
                divisions[int(ticks) - 1] = label
    assert m.r32(0x400d40a6) == m.symbols['ap_speed'], 'SPD descriptor not installed'
    for value in (*range(96), 96, 127, 0xffffffff):
        m.write(0x20000, b'!' * 32)
        m.call(0x4003b840, 0x20008, value)
        native = m.read(0x20008, 16).split(b'\0')[0].decode()
        m.write(0x20000, b'!' * 32)
        m.call(m.r32(0x400d40a6), 0x20008, value)
        expected = divisions.get(value, native).encode() + b'\0'
        assert m.read(0x20000, 32) == b'!' * 8 + expected + b'!' * (24-len(expected)), value
    print('  [PASS] installed SPD formatter: all 96 values, musical duration oracle, native fallback, invalid values, buffer bounds and ABI')
    for bank in (0, 15):
        for part in range(4):
            for track in range(8):
                for i, (name, _, _) in enumerate(PATTERNS):
                    m.seed(bank, part, track)
                    before = m.state()
                    m.call('ap_apply', i)
                    assert m.state() == m.expected(before, i), (bank, part, track, name)
                    assert m.call('ap_match') == i, name
                    assert m.read(0x100b145e, 1) == bytes([0x80 | (1 << part)])
                    assert m.r32(0x100f8598) == 1
                    m.call('ap_title', 0, 0, 0)
                    assert m.title == 'ARP A:' + name
    print(f'  [PASS] {len(PATTERNS) * 64} applications: rhythms, exact Part/CS1/live write boundaries, dirty bits, titles, ABI and interrupt mask')
    m.seed(); m.call('ap_apply', 4)
    for offset in (0x8f270, 0x905a2, 0x905b2, 0x905c1):
        m.call('ap_apply', 4)
        m.write(DB + offset, [m.read(DB + offset, 1)[0] ^ 1])
        assert m.call('ap_match') == 0xffffffff
        m.call('ap_title', 0, 0, 0); assert m.title == 'ARP A:CUSTOM'
    before = m.state()
    for i in (len(PATTERNS), 0xffffffff):
        m.call('ap_apply', i); assert m.state() == before
    for addr, value, width in ((0x100b14cc, 8, 1), (0x100b14cf, 4, 1), (0x46c82456, DB + 1, 4)):
        previous = m.read(addr, width)
        m.write(addr, value.to_bytes(width, 'big'))
        m.call('ap_apply', 0); assert m.state() == before
        m.write(addr, previous)
    # Real native entry, including the detour and its stock return path.
    m.seed(); before = m.state(); m.call(0x4007a2ec, 0, 0)
    assert m.state() == before
    assert m.call('ap_match') == 0xffffffff
    m.call(0x4007a2ec, 0, 1); assert m.call('ap_match') == 0
    for i in range(1, len(PATTERNS)):
        m.call(0x4007a2ec, 0, 127); assert m.call('ap_match') == i
    before = m.state(); m.call(0x4007a2ec, 0, 1); assert m.state() == before
    for i in range(len(PATTERNS) - 2, -1, -1):
        m.call(0x4007a2ec, 0, -1); assert m.call('ap_match') == i
    before = m.state(); m.call(0x4007a2ec, 0, -1); assert m.state() == before
    print('  [PASS] CUSTOM recognition, invalid inputs, real A handler, zero movement, fast turns and end stops')
    # Compare unmodified native control paths byte-for-byte with this detour
    # temporarily restored to stock. Both execute the same built OS routines.
    site = 0x4007a2fc
    patched = m.read(site, 8)
    original = (ROOT / 'out/raw/section_3_MAIN_OS.bin').read_bytes()[site - 0x40000400:site - 0x40000400 + 8]
    for routine, args in ((0x4007a2ec, (2, -1)), (0x4007a2ec, (5, 1)),
                          (0x4007a2ec, (6, 12)), (0x4007a7d4, (0x34,)),
                          (0x4007a7d4, (0x21,))):
        outputs = []
        for code in (patched, original):
            m.write(site, code)
            # Unicorn's translated blocks must follow the changed hook.
            m.uc.ctl_remove_cache(site, site + 8)
            m.seed(); m.call('ap_apply', 4)
            m.write(DB + 0x8f273, [1])
            m.write(0x460e73a0, b'\0\1')
            m.call(routine, *args)
            outputs.append(m.state())
        assert outputs[0] == outputs[1], (hex(routine), args)
    m.write(site, patched); m.uc.ctl_remove_cache(site, site + 8)
    print('  [PASS] C length, F key, LEVEL offsets and both native rotations equal stock')


if __name__ == '__main__': main()
