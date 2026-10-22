"""Stock effects with display-only musical units."""
from remix.schema import Proof, Remix
REMIX = Remix(
    name="musical-units", family="mods", proof=Proof.CHECK,
    proof_note="Linked formatter checks and native panel captures; no hardware acceptance.",
    doc="Stock effects with musical timing, MIDI note/arp, sample retrigger and recorder fade units.",
    modules=("MUSICAL UNITS", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
