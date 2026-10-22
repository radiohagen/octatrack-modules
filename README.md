# Octatrack modules

Source for MIDI Scales, Loopback, Follow and Harmony, maintained by
[radiohagen](https://github.com/radiohagen).
[Octabam](https://github.com/sambanks/octabam) supplies the firmware builder
and shared platform.

[Euclid LFO](modules/euclid-lfo/README.md) adds independent fixed-step rhythmic
modulation to native audio and MIDI LFOs. Its [scoped integration](integration/EUCLID_LFO.md)
is separate from the existing MIDI package and does not advance that package's pin.

- [Modules and controls](modules/README.md)
- [Build and source integration](integration/README.md)
- [Licensing and attribution](THIRD_PARTY.md)

The repository includes the modules' Part storage, retained-memory support
and shared-event callbacks. Firmware, samples and device projects are not distributed.

[Developer notes and verification](DEVELOPMENT.md).
