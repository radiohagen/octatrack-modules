"""Rhythmic presets in the native MIDI ARP SETUP editor, on encoder A."""
from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof, SymbolRef

MODULE = Module(
    name='midi-arp-presets', key='MIDI ARP PRESETS', kind=Kind.CF_PATCH,
    category=Category.MIDI_USB, author='Mattias Wolff',
    author_url='https://github.com/mattiaswolff/octabam',
    proof=Proof.PORT, proof_note='Native panel, save/reload and held-root MIDI capture under the port; hardware untested.',
    doc='Encoder A on MIDI ARP SETUP loads 17 editable rhythmic presets; C LEN and F KEY remain native.',
    linked=(Linked('midiarppresets', 'modules/midi-arp-presets/presets.s', dram=True),),
    symbol_refs=(SymbolRef(0x400d40a6, 0x4003b840, 'midiarppresets', 'ap_speed',
                           'ARP SPD musical divisions; native fallback for unusual ticks'),),
    detours=(
        Detour(0x4007a2fc, bytes.fromhex('7202b280660000e0'),
               'midiarppresets', 'ap_encoder', 'ARP SETUP A preset selection', pad_to=8),
        Detour(0x40079d68, bytes.fromhex('4eb9400570b8'),
               'midiarppresets', 'ap_title', 'ARP SETUP title identifies current rhythm or CUSTOM', kind='jsr'),
    ),
    gates=(Gate('tools/verify/verify_midi_arp_presets.py', stage='image', venv=True),
           Gate('tools/verify/verify_midi_arp_presets_port.py', stage='image', venv=True)),
)
