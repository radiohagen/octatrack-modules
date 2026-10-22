# Selected modules

| Module | Role |
|---|---|
| [Euclid LFO](euclid-lfo/README.md) | Fixed-duration Euclidean steps and accents for native audio/MIDI LFO destinations; separate test integration |
| MIDI Scales | Seven diatonic modes in native MIDI ARP KEY |
| MIDI Loopback | Per-Part EXT / INT / BOTH routing |
| MIDI Follow | Root following, register, response and mute behavior |
| MIDI Harmony | Degree roots, chords, Chord Play, voicing and retained steps |
| MIDI Part State | Shared native Part settings and coherent copy/clear |
| MIDI SRAM | Protected retained native MIDI step padding |
| Harmony Follow | Shared transport and successful-note events for Harmony and Follow |
| Harmony PLOCKS | Shared editing and copy hooks beside upstream PLOCKS |
| MIDI Loopback Scenes | Scenes/USB producer routing through Loopback |
| PIO Write Fix | Existing first-sector ordering fix, without STEM REC |
| Quantizer MIDI Drawer | Preserve native MIDI octave rendering beside Quantizer |

The first four provide player controls. The others provide shared storage,
integration or compatibility support. Open a module's README for its behavior.
