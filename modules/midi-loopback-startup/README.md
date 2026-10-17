# MIDI Loopback startup sequence

A silent call/return sequence before native DSP upload prevents the observed
cold-start logo stall in the tested MIDI Loopback composition on one MKII.
It runs only at startup, preserves native continuation registers/CCR/SP,
uses 32 bytes of existing stack, and performs no MIDI UART access. It adds
no runtime allocation and no work to normal MIDI delivery.

This is an **empirical workaround, with the cause still open**. Its exact
instruction order, 848-byte static footprint and uncalled 18-byte runtime
tail preserve the tested image layout and compression. The tail has no hook;
native boot calls Part activation directly. Removing apparent dead code or
replacing the calls with an instruction-count delay changes the qualification.

The sequence derives from sanderlegit's BOOT TRACE, with transmission and
other hooks removed. It is a fixed selection with no diagnostic build flags.
Loopback requires it; the standalone remix includes it. Other compositions,
MK I units and other physical devices require their own boot checks.

The startup gate compares 128 native entry states, pins the static bytes,
checks the exact stack accesses and direct Part activation, and exercises
96 native peripheral-wait cases with four negative controls. These checks
cannot reproduce power-off-dependent hardware state or establish root cause.

See [Loopback hardware evidence](../midi-loopback/HARDWARE.md) for image
identity and the scope of physical acceptance.
