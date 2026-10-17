"""Silent startup sequence preserving the hardware-tested Loopback composition."""
from pathlib import Path
from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof
ROOT = Path(__file__).resolve().parent
MODULE = Module(
    name="midi-loopback-startup", key="MIDI LOOPBACK STARTUP", kind=Kind.CF_PATCH,
    category=Category.REFERENCE, author="radiohagen",
    author_url="https://github.com/radiohagen/octatrack-modules",
    proof=Proof.HARDWARE,
    proof_note="One MKII, 17 Oct 2026: silent startup composition boots after five minutes off; cause open.",
    doc="Silent DSP-upload entry workaround for the observed Loopback cold-start stall.",
    requires=("MIDI PART STATE",),
    linked=(Linked("loopback_startup", str(ROOT/'startup.s'), cpu="5475"),
            Linked("loopback_startup_layout", str(ROOT/'layout.s'), dram=True,
                   defsyms=(("startup_trace", 0),))),
    detours=(Detour(0x40001e50, bytes.fromhex("420013c0fc0a400c"),
                    "loopback_startup", "startup_upload",
                    "silent call/stack sequence before native DSP upload", pad_to=8),),
    gates=(Gate("tools/verify/verify_midi_loopback_startup.py", stage="image", venv=True),),
)
