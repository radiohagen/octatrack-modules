"""Latest BottleService and personal MIDI modules, with full retained capacities."""
from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    name="mattias-bottleservice",
    family="rig", proof=Proof.CHECK, proof_note='verify_integrated_retention_port: full capacity under the port; hardware untested',
    doc="Full BottleService, KITS and MIDI SCENES with MIDI Follow, Scales, Harmony SIZE/CHORD PLAY, MIDI Loopback, RLEN PLEN, Tuner, FM Synth and ARP PRESETS; full unsaved capacities.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP", "CC FEEDBACK", "MODE DEFAULTS", "RIG HOSTS", "TEMPO BUS",
             "USB MIDI", "USB AUDIO OUT",
             "STORE", "KITS", "MIDI SCENES", "MIDI SRAM",
             "ARP PRESETS", "MIDI PART STATE", "MIDI FOLLOW", "MIDI SCALES", "MIDI HARMONY", "HARMONY PLOCKS",
             "RLEN PLEN", "TUNER", "SYNTH MACHINE", "MIDI LOOPBACK", "MIDI LOOPBACK SCENES",
             "SCENES P2", "PLOCKS P2",
             "DELAY",    # the stock DELAY keeps its chooser row: T8 hosts it (4 Oct 2026)
             "FX2 LOCK"),   # and the chooser cannot change any track's FX2 (4 Oct 2026, image A1)
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    host_slots=(("DELAY SERVER", 2), ("REVERB SERVER", 2)),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
    settings={("octabam.usb-audio-out", "LAYOUT"): Pin("MASTER"),
              ('mattias.plocks-p2','RETENTION'): Pin('MIDI POOL'),
              ('mattias.midi-harmony','RETENTION'): Pin('SHARED')},
)
