# midi-part-state implementation and verification

Shared native Part access and coherent publication, introduced with MIDI
Loopback as its first consumer. It adds no panel control and needs no KITS.

Working native Parts are authoritative. UI writes use the selected working
Part; playback reads each track's playing context. Writes update native
working bytes, the current-bank CS1 mirror and native dirty bits. Native
Save/Reload and project storage carry those bytes without a companion file.

SETUP offset 12 is a shared flags byte. Loopback owns bits 2–3 for DEST
(EXT/INT/BOTH); value 3 and invalid flags read as EXT. Bits 0–1 are preserved
for future consumers. The native range is 0..15, declared by this module,
and fresh Parts initialize it to zero. Firmware without Loopback does not
interpret DEST; use EXT before returning to stock behavior.

Cold ROM entry gates retain native copy/initialization before the platform
runtime loads. A native post-loader call then activates the DRAM targets.
While a native copy or initialization replaces working Parts, explicit-context
readers see a complete outgoing snapshot of all four MIDI SETUP arrays.
Snapshot preparation and native copying keep interrupts enabled; final
publication uses a short interrupt mask without callbacks or native copying.
Nested operations retain the outer snapshot. Native arguments and register
returns are preserved. Condition codes are outside the C calling contract.

Direct readers of native memory do not use the snapshot. New clients must
use the explicit-context API. A replaced Part advances its runtime epoch;
ordinary setting edits do not. Runtime note ownership remains the consumer's
responsibility. Bulk operations crossing bank boundaries and live cross-project
transitions require separate qualification.

`verify_midi_part.py` checks distinct UI/playback contexts, bounded writes and
mirrors. `verify_midi_part_copy.py` compares native copy/initialization bytes,
registers and interrupt state, cold entry, guards and interrupted publication.
`verify_midi_part_port.py --project DIR` executes native Save/Reload/Clear/Paste
under the firmware emulator on a disposable virtual card. Loopback's UI test
covers project save/load and retained resume. No hardware acceptance is claimed.

The source is extracted from integration `8f8e00d061d17a890a3b01d5f340492f912712e2`.
Future Harmony/SRAM conditionals remain dormant source; the Follow/Harmony
NOTE SETUP staging hook is omitted from this standalone contribution.
