# Licensing and attribution

The imported MIDI and integration source originates from Mattias Wolff's
Octabam work. Original author names and notices are preserved, including the
PIO fix's yvesrosius attribution. Imported files retain the Octabam MIT terms
in [the original licence](licenses/octabam-MIT.txt), also reproduced as the
root [LICENSE](LICENSE) for repository tooling. Hosting under radiohagen
updates operational source links but does not change authorship or relabel other contributors' work.

Repository scaffolding is adapted from the owner's existing octatrack-modules
repository. Its source provenance is recorded separately. No third-party
source is relicensed by this migration. The original repositories remain intact.
No Elektron firmware, generated firmware, samples or device projects are included.

The separately authorized Supersaw experiment uses its own mathematical oscillator
tables and fixed-point engine. Its CPU SEM filter adapts the equations and
resonance mapping of sambanks' SPECTRUM module in Octabam (MIT), whose design
references Vadim Zavalishin and audiojs/filter (MIT). The reference gate runs the
actual SPECTRUM DSP implementation; this is not an OP-1 source-code import.
