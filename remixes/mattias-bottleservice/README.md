# Mattias BottleService integration

Branch ownership, future changes and release steps are documented in the
[fork workflow](https://github.com/mattiaswolff/octabam/blob/94fa3cdcb893c4f48a15533f1a49ea3546d7d12f/docs/guide/FORK_WORKFLOW.md).

## OCTABAM84 MIDI Arp Presets package

Adds the separate [MIDI Arp Presets](../../modules/midi-arp-presets/README.md) module
to the complete OCTABAM83 selection. MIDI ARP SETUP: turn A to load one of
16 rhythms, then edit steps natively; C is LEN and F is KEY, including the
existing MIDI Scales modes. Presets replace the current arp, so copy an
existing custom arp before browsing. Selection is immediate and keeps phase.
ARP MAIN SPD uses exact musical labels: x6 becomes 1/16, x12 becomes 1/8;
T means triplet and D dotted. Unusual values keep their native xN readout.

The release receipt records the exact source, image, standard checks,
combined emulator checks and package identities. Hardware acceptance and
the previously reported boot symptom remain open. No card copy or upgrade
is part of this package release.

## OCTABAM83 Synth and MIDI Loopback package

Adds SYNTH MACHINE and MIDI LOOPBACK (source `9d5682fd`) to the OCTABAM82
selection, with a dedicated MIDI LOOPBACK SCENES compatibility bridge.
SCALE QUANTIZER is excluded. The
TEMPO BUS screen remains available: its code now lives in DRAM, leaving
the Synth page's ROM location free.

The bridge routes MIDI Scenes sequencer and crossfader CCs using the actual
source Part's Loopback DEST, before USB/DIN output. KITS and MIDI SCENES
source is unchanged. CC Feedback is a separate audio-output path; use
AUDIO CC OUT = INT to keep that feedback internal.

The local package includes `AUDIO/FMSYNTH.wav`, four seconds of mono silence
at 44.1 kHz / 16-bit PCM. Copy it into the set's AUDIO folder, load it into
a FLEX slot and assign that slot to a FLEX track. The filename activates
the synth; the marker duration does not limit note length. No automatic
card copy, slot assignment or firmware installation occurs.

The final MAIN OS SHA-256 is
`21de653cff0bc39b67070ece2886b90f5e0b2d6dbae85f2ae405815276b8661e`.
Shared checks, 42 image gates and the focused emulator checks passed,
including Synth/Loopback interaction, full-capacity retention, KITS/Scenes
recall, Scenes persistence and protected-memory writes. TEMPO SYNC's
exported entry points now have unique names: the former `cave` name
collided with RLEN PLEN's local symbol and left DSP-facing FX2 IDs zero.
The installed-hook and Synth gates check actual FX2 records and audible
Synth sends through both bus hosts. Package receipts record fixture and
coverage gaps; physical playback, installation and hardware timing remain
untested. The previously reported first-power-on logo hang is unresolved.

## OCTABAM82 baseline

The OCTABAM82 candidate integrates upstream `6e4aeb76` with the prepared MIDI
contribution stack and the latest SCENES/PLOCKS fixture corrections. Contains full
BottleService (USB MIDI, USB AUDIO OUT MASTER, CC MAP and CC FEEDBACK),
KITS, current MIDI SCENES, SCENES P2, PLOCKS P2, MIDI Follow, Scales,
Harmony SIZE/CHORD PLAY, RLEN PLEN and TUNER. MIDI Loopback is
excluded. KITS and MIDI SCENES source remains upstream's.

Build: `make bus REMIX=mattias-bottleservice`.

## Retained capacity

| Store | Retained allocation | Capacity |
|---|---|---|
| PLOCKS P2 | 20-byte header at `0x100f8600`, 15,448 bytes in protected MIDI padding | 10,234 locks |
| Harmony | 10,400 bytes at `0x100f8620` | All 8,192 step tuples |
| MIDI SCENES | Upstream `0x100fbdf0..0x100ffe00` | Four full 4,096-byte tables |
| KITS | Upstream allocations | Unchanged |

The earlier P2 compression remains in use. The additional 16,384-byte
[MIDI SRAM pool](../../modules/midi-sram/README.md) protects unused MIDI step
fields from native copy/clear operations. Audio sample-lock fields remain
native. Ordinary upstream PLOCKS keeps its original default allocation.
P2LK v1, HDP3 and HDN3 formats and all capacities are preserved by the
STORE-client revision. Acceptance targets current-format projects.

## Shared persistence

Harmony registers `ch_st_*` callbacks with [STORE](https://github.com/mattiaswolff/octabam/blob/94fa3cdcb893c4f48a15533f1a49ea3546d7d12f/modules/store/README.md).
It no longer replaces STORE's hooks or patches native load/new-project call
sites: 18 Harmony persistence detours and nine STORE overrides are removed.
The Harmony/P2 bridge now handles only editing and pattern/track copies.

STORE supplies optional checked callbacks before bank writes and copies,
checked completion after successful copies, and notification after native
NEW PROJECT. Save failures retain the existing protection for stored bank
backups. A native-copy failure now suppresses every companion-copy
notification, fixing the prior P2 backup overwrite on that error path.

Optional callback code compiles out when unused. The eight original STORE
client combinations retain their generated tables and callback ABI; their
only shared behavior change is the native-copy failure check.

## Current convention audit

The MIDI modules use declared DRAM units, asserted native hooks and ledger
claims for Part bytes and retained SRAM. Early Part-copy wrappers stay in
ROM and publish their DRAM targets only after the loader returns. Runtime
initialization does not assume zero-filled BSS; ownership and publication
markers are loaded data, and large working tables have explicit initialization.
Follow and Scales use native Part storage. Harmony uses STORE for persistence
and the dedicated bridge only for shared editing/copy hooks. Empty companion
markers now propagate close failures through STORE, matching the existing
open/write error handling.

PAGE uses the native handler. The deferred chord scheduler and its system-task
hook have been removed; direct CHORD PLAY emits the complete chord immediately.
Generated code is still checked against its C source. No KITS or MIDI SCENES
implementation changes were needed for this revision.

## Verification

OCTABAM82's MAIN OS SHA-256 is
`0e8349a9441913e0ad11f5841dad0c5af4196c4f6ce66ac4192eebba43085554`.
The shared and per-remix checks passed on upstream `6e4aeb76`. Separate
full-firmware emulator runs passed full-capacity retention, 18 KITS/Scenes
recalls, 12 SIZE/audio-Scenes combinations, 13 eight-track MIDI scenarios,
and nine Harmony degree/persistence groups. Project routing, MODE DEFAULTS,
TEMPO BUS, FX2 LOCK, MIDI SCENES persistence, SCENES P2 and PLOCKS P2 also
passed their focused gates. BIN/SYX decoding and RMX equality identify the
same tested image.

The local package's `release.json` and `evidence/` record commands, results
and skips. The MIDI SCENES fixture needed neutral audio FX parameters and
pattern 2 assigned to Part 2; its unchanged assertions then passed, including
stock Part-byte equality. The full upstream KITS suite and its private import
and stranded-project fixtures were not run; the combined recall and MIDI
SCENES Kit save/load cases were. These are deterministic host results, not
physical MIDI/USB timing, hardware playback or boot acceptance.

## Boot investigation

The first-power-on logo hang remains unresolved, including with USB unplugged.
This release is not a confirmed boot fix. The repeatable host diagnostic
`python3 tools/verify/verify_midi_boot.py` checks dirty runtime memory (zero,
0xff, 0xa5), the native boot logo, DSP uploads, panel handshake and audio frames.
It writes `out/midi-boot/receipt.json` and per-case logs. These are emulator
reports; the port cannot model hardware caches or electrical startup timing.

A USB-readable device log is **not implemented**. The failure may precede
filesystem initialization, so writing a file from the early loader is not a
safe diagnostic. A viable design would keep a bounded breadcrumb in retained
SRAM, preserve the previous attempt during the next startup, then export from
the engine task after the filesystem mounts. The spare 3,900-byte region is
large enough in this selection, but early-boot/reset survival and an exporter
that also runs after a retained resume still need validation. STORE's project
file callbacks alone do not cover a hang before the runtime loads.

Upstream BOOT TRACE offers an existing DIN MIDI probe for boot stages. It
cannot simply be enabled in this selection: its DSP-return hook collides with
MIDI PART STATE activation. A diagnostic integration must preserve both paths
and validate its placement before being deployed. See the
[failure register](https://github.com/mattiaswolff/octabam/blob/94fa3cdcb893c4f48a15533f1a49ea3546d7d12f/docs/contributing/FAILURE_MODES.md).
