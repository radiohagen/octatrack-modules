# Octatrack modules

Source for MIDI Scales, Loopback, Follow, Harmony and Musical Units, maintained by
[radiohagen](https://github.com/radiohagen).
[Octabam](https://github.com/sambanks/octabam) supplies the firmware builder
and shared platform.

[Euclid LFO](modules/euclid-lfo/README.md) adds independent fixed-step rhythmic
modulation to native audio and MIDI LFOs. Its [scoped integration](integration/EUCLID_LFO.md)
is separate from the existing MIDI package and does not advance that package's pin.

[Sophie](modules/sophie/README.md) is an experimental mono percussion voice
for the Synth Machine transport. Its source is separate from the MIDI package
and requires a Sophie-enabled Octabam integration to build firmware.

- [Modules and controls](modules/README.md)
- [Build and source integration](integration/README.md)
- [MIDI Follow integration](integration/midi-follow.md)
- [Licensing and attribution](THIRD_PARTY.md)

The repository includes the modules' Part storage, retained-memory support
and shared-event callbacks. Firmware, samples and device projects are not distributed.

[Developer notes and verification](DEVELOPMENT.md).

The separately authorized [CPU Supersaw experiment](modules/supersaw/README.md)
keeps both FX slots available. It is outside the MIDI upstream series.
