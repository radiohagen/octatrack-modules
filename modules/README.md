# Selected modules

| Module | Role |
|---|---|
| MIDI Scales | Seven diatonic modes in native MIDI ARP KEY |
| MIDI Loopback | Per-Part EXT / INT / BOTH routing |
| MIDI Follow | Root following, register, response and mute behavior |
| MIDI Harmony | Degree roots, chords, Chord Play, voicing and retained steps |
| MIDI Part State | Shared native Part settings and coherent copy/clear |
| MIDI SRAM | Protected retained native MIDI step padding |
| Harmony PLOCKS | Shared editing and copy hooks beside upstream PLOCKS |
| MIDI Loopback Scenes | Scenes/USB producer routing through Loopback |
| PIO Write Fix | Existing first-sector ordering fix, without STEM REC |
| Quantizer MIDI Drawer | Preserve native MIDI octave rendering beside Quantizer |

The first four are user-facing features. The others are support or compatibility
changes; the two general fixes should be proposed separately upstream.

No synth additions, MIDI Arp Presets/ARP templates or POST FADER are selected.
Module READMEs retain historical measurements; consult the current verification
record before treating them as evidence for a new build.
