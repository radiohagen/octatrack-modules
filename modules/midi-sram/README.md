# Protected MIDI retained pool

Opt-in support module for compositions that need additional retained capacity.
Select `MIDI SRAM` with `MIDI PART STATE`. It adds no panel control and provides
16,384 retained bytes in fields 30/31 of each native MIDI step record in the
current-bank CS1 mirror: 16 patterns × 8 tracks × 64 steps × 2 bytes.
Audio step fields are untouched: audio field 31 is a sample lock.

The pool exists only in SRAM. The MIDI PART STATE native-copy boundary skips
these destinations and returns `0xff` for these source bytes, so pool data
never enters native DRAM, clipboards or bank files. Eight MIDI-only direct
write loops stop at the 30 parameter fields. All other native bytes retain
the stock copy/clear behavior. The cold ROM boundary remains stock until the
platform loader has activated the runtime. A whole-CS1 reset invalidates the
client headers; an ordinary bank copy must preserve the pool.

`rp_read` and `rp_write` check offset and length before every transfer. They
do not publish a checkpoint: the client owns its dedicated header, checksum,
writer serialization and final atomic magic store. PLOCKS P2 uses 15,448
payload bytes; its header lives outside the pool. Clients must not bypass
this allocation or assume that native padding in DRAM is retained storage.

Each two-byte range is declared individually in the resource ledger. Do not
replace these claims with an assertion that the intervening stock data is
unused. New stock/module writers into the pool invalidate this design and
must be added to its protection and verification before composition.

Validation commands, after `make bus REMIX=midi-sram`:

```
.venv/bin/python tools/verify/verify_midi_sram.py
.venv/bin/python tools/verify/verify_midi_sram_port.py --project <fixture-project>
```

The linked gate checks bounded I/O, native copies and track clears with an
observer that rejects every pool write. The port gate compares native data
against stock across complete operations and retained restarts. The combined
maximum-capacity gate is `tools/verify/verify_integrated_retention_port.py`,
run against `mattias-bottleservice`. Receipts are under `out/`. No physical
battery retention, firmware installation or hardware timing is established.

## Source and acceptance

Edit `pool.c`, then run `python3 modules/midi-sram/generate.py` and the same
command with `--check`. Callers must handle a rejected bounds check; a failed
transfer must never publish a valid client header. Hardware cold starts,
long power-offs and interrupted checkpoints remain acceptance work. A port
restart models retained bytes; it does not prove battery or reset behavior.

The full-firmware commands above share Harmony test helpers and are available
in the complete integration stack. The standalone branch includes its own
linked-code gates through `make check`; it has no runtime dependency on Harmony.
