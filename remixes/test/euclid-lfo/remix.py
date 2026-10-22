"""Independent Euclid LFO with all stock effects retained."""
from remix.schema import Proof, Remix
REMIX=Remix(
    name="euclid-lfo", family="mods", proof=Proof.CHECK,
    proof_note="emulator tested; no hardware acceptance", doc="Euclidean audio and MIDI LFOs; stock FX.",
    modules=("EUCLID LFO", "STORE", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"), fallback="NONE",
)
