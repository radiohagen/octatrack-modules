"""Offline PR 542 send-mute experiment on current upstream BottleService."""

from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    name="send-return-poc",
    family="rig", proof=Proof.PORT, proof_note="current upstream BottleService with the PR 542 POST FADER technique; offline PoC",
    doc="Current BottleService plus POST FADER: mute/solo-aware bus sends with LEVEL attenuation; engines remain on T1/T5, no RETURNS port.",
    modules=("POST FADER", "REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP", "CC FEEDBACK", "MODE DEFAULTS", "RIG HOSTS", "TEMPO BUS",
             "USB MIDI", "USB AUDIO OUT",
             "STORE", "KITS",
             "SCENES P2", "PLOCKS P2",
             "DELAY",    # the stock DELAY keeps its chooser row: T8 hosts it (4 Oct 2026)
             "FX2 LOCK"),   # and the chooser cannot change any track's FX2 (4 Oct 2026, image A1)
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    host_slots=(("DELAY SERVER", 2), ("REVERB SERVER", 2)),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
    settings={("octabam.usb-audio-out", "LAYOUT"): Pin("MASTER")},
)
