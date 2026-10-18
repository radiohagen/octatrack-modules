"""Shared native Part access and coherent publication for MIDI modules."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent

from remix.schema import Category, Claims, Detour, Gate, Kind, Linked, Module, Poke, Proof

MODULE = Module(
    name='midi-part-state', key='MIDI PART STATE', kind=Kind.CF_PATCH,
    category=Category.PARTS, author='radiohagen',
    author_url='https://github.com/radiohagen/octatrack-modules', proof=Proof.HARDWARE,
    proof_note='radiohagen Octatrack MKII: Part/project persistence through MIDI Loopback; other consumers unqualified',
    doc='Shared native Part settings and coherent copy/clear publication; no KITS dependency.',
    linked=(Linked('midipartentry', str(ROOT / 'entry.s'),
                   # Canonical author-reference addresses only; every final
                   # image must resolve both from its selected runtime.
                   defsyms=(('mp_native_copy',0x40a9582e),('mp_native_init',0x40a95860)),
                   runtime_refs=(('mp_native_copy','midipartcopy','mp_native_copy'),
                                 ('mp_native_init','midipartcopy','mp_native_init'))),
            Linked('midipart', str(ROOT / 'part.s'), dram=True,
                   include=lambda modules: '.set MP_DEFINE,1\n'),
            Linked('midipartcopy', str(ROOT / 'part-copy.s'), dram=True,
                   defsyms=(('mp_copy_target',0),('mp_init_target',0)),
                   include=lambda modules: '.set MP_DEFINE,1\n' + ('.set HAVE_HARMONY,1\n' if 'MIDI HARMONY' in modules else '') + ('.set HAVE_MIDI_SRAM,1\n' if 'MIDI SRAM' in modules else ''))),
    detours=(Detour(0x40000512, bytes.fromhex('4eb94000f938'),
                    'midipartentry', 'mp_resident_activate', 'enable Part boundaries after native platform load', kind='jsr'),
             Detour(0x40020898, bytes.fromhex('2f02226f0008'),
                    'midipartentry', 'mp_copy_entry', 'coherent native MIDI Part copies'),
             Detour(0x40005638, bytes.fromhex('4fefffa848d77cfc'),
                    'midipartentry', 'mp_init_entry', 'coherent native MIDI Part initialization', pad_to=8)),
    pokes=(Poke(0x400d4082, bytes.fromhex('00000001'), bytes.fromhex('00000010'), 'Follow/Loopback Part flags range'),),
    claims=Claims(part_window=tuple((0x4e2+36*t+12, 1, 'shared MIDI Part flags') for t in range(8))),
    gates=(Gate('tools/verify/verify_midi_part.py', stage='image', venv=True),
           Gate('tools/verify/verify_midi_part_copy.py', stage='image', venv=True)),
)
