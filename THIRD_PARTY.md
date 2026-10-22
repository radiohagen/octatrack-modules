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

Sophie adapts [soejrd/digisophie](https://github.com/soejrd/digisophie).
The unmodified MIT-licensed engine is pinned as a submodule at
`ce17b9e4868027bafe8684054b45f28ea368bd7c`; the Octatrack adapter
and its source provenance remain separate from the engine.

Euclid LFO is new radiohagen ColdFire source. Its pulse distribution, random
generation and envelope curves are adapted from Jannik Aßfalg (`repeat98`)'s
EUCLID effect in Octabam, originally introduced in commit
`da7fa67589905dfcf0dbd6629c3e72e1c69f96c2`. The effect itself is not included or
modified by this module. The existing MIT terms and attribution are preserved.

The separately authorized Supersaw experiment uses its own mathematical oscillator
tables and fixed-point engine. Its CPU SEM filter adapts the equations and
resonance mapping of sambanks' SPECTRUM module in Octabam (MIT), whose design
references Vadim Zavalishin and audiojs/filter (MIT). The reference gate runs the
actual SPECTRUM DSP implementation; this is not an OP-1 source-code import.
