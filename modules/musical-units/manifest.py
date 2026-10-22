"""Display-only musical periods; native values, editors and engines stay stock."""
from remix.schema import Category, FormatterReg, Gate, Kind, Linked, Module, Proof, SymbolRef

def _include(modules, _remix):
    # Existing formatter registrations are explicit adapters. Refuse another
    # adapter for the same stock slot instead of relying on link order.
    for key, module in modules.items():
        if key == "MUSICAL UNITS":
            continue
        for unit in (*module.linked, *module.cf_patches):
            registration = unit.registers_formatter
            if registration and registration.module == "DELAY" and registration.slot == 0:
                raise ValueError(f"MUSICAL UNITS: DELAY TIME already has a formatter from {key}")
    return ""


# base, slot, native formatter, adapter, native widget. Preserve widget type.
_ADAPTERS = (
    (0x400d3e06, 2, 0x4003bb28, "mu_note_length", 0x400467a4),
    (0x400d3f98, 5, 0x4003bb28, "mu_note_length", 0),
    (0x400d3f98, 3, 0x4003b840, "mu_arp_speed", 0x400467a4),
    (0x400d3f98, 0, 0x4003c7a0, "mu_transpose", 0),
    (0x400d3c74, 6, 0x4003b18c, "mu_record_fade", 0),
    (0x400d3c74, 7, 0x4003b18c, "mu_record_fade", 0),
    (0x400d2fe4, 5, 0x4003b398, "mu_retrig", 0),
    (0x400d3176, 5, 0x4003b398, "mu_retrig", 0),
)

MODULE = Module(
    name="musical-units", key="MUSICAL UNITS", kind=Kind.CF_PATCH,
    category=Category.UTILITIES, author="radiohagen", author_url="https://github.com/radiohagen",
    doc="Musical/physical units for LFOs, delay, MIDI note lengths, arpeggiator speed/transpose, sample retriggers and recorder fades. Display only.",
    proof=Proof.CHECK, proof_note="Linked formatter checks and native panel captures; no hardware acceptance.",
    linked=(Linked("musicalunits", "modules/musical-units/units.s", dram=True, include=_include,
                   registers_formatter=FormatterReg(module="DELAY", slot=0, symbol="mu_delay")),),
    symbol_refs=tuple(
        SymbolRef(base + 0x102 + slot * 4, 0, "musicalunits", "mu_" + kind + "_" + name,
                  kind + " LFO " + name + " cycle duration")
        for kind, base in (("audio", 0x400d37be), ("midi", 0x400d412a))
        for slot, name in ((0,"one"),(1,"two"),(2,"three"),(10,"setup"))
    ) + tuple(
        SymbolRef(base + 0x132 + slot * 4, 0, "musicalunits", "mu_widget",
                  "musical-unit dial: full-width held-lock highlight")
        for base, slots in ((0x400d37be, (0,1,2,10)), (0x400d412a, (0,1,2,10)),
                            (0x400d4a96, (0,)))
        for slot in slots
    ) + tuple(
        SymbolRef(base + 0x102 + slot * 4, native, "musicalunits", symbol,
                  "musical-unit parameter formatter")
        for base, slot, native, symbol, widget in _ADAPTERS
    ) + tuple(
        SymbolRef(base + 0x132 + slot * 4, widget, "musicalunits",
                  "mu_bar_widget" if widget else "mu_widget",
                  "musical-unit widget: preserve native shape and widen lock highlight")
        for base, slot, native, symbol, widget in _ADAPTERS
    ),
    gates=(Gate("tools/verify/verify_musical_units.py", stage="image", venv=True),),
)
