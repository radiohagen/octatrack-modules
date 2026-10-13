"""Standalone MIDI ARP PRESETS with stock audio effects."""
from remix.schema import Proof, Remix

REMIX = Remix(
    name='midi-arp-presets', family='mods', proof=Proof.PORT,
    proof_note='Native panel, save/reload and MIDI capture under the port; hardware untested.',
    doc='Native MIDI ARP SETUP with a bank of editable rhythms on encoder A.',
    modules=('MIDI ARP PRESETS', 'FILTER', 'EQUALIZER', 'DJ EQ', 'PHASER', 'FLANGER',
             'CHORUS', 'SPATIALIZER', 'COMB FILTER', 'COMPRESSOR', 'LO-FI',
             'DELAY', 'PLATE REV', 'SPRING REV', 'DARK REV'),
    fallback='NONE',
)
