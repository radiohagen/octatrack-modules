"""Independent Euclidean waveform and editor for audio and MIDI LFOs."""
from remix.schema import Category, Claims, Detour, Gate, Kind, Linked, Module, Poke, Proof, SymbolRef, TableGrow

H=bytes.fromhex
MODULE=Module(
    name="euclid-lfo", key="EUCLID LFO", kind=Kind.CF_PATCH,
    category=Category.TRACK, author="radiohagen",
    author_url="https://github.com/radiohagen",
    proof=Proof.CHECK, proof_note="emulator tested; no hardware acceptance",
    doc="Independent 1–16-step Euclidean audio/MIDI LFO with accents and native routing.",
    requires=("STORE",),
    gates=(Gate("tools/verify/verify_euclid_lfo.py",stage="image"),),
    # Upper portion of the original PLOCKS reservation. The integration selects
    # bounded compressed PLOCKS retention when both modules are present.
    claims=Claims(sram=((0x100fa5e0,6160,"Euclid LFO current-bank retained journal"),)),
    linked=(Linked("eul", "modules/euclid-lfo/control.s", cpu="5475", dram=True),),
    detours=(
        Detour(0x40003c4a,H("274600182e80"),"eul","eul_clock_audio",
               "Scale EUCLID step clock before native trigger and cycle handling"),
        Detour(0x4000cfe4,H("274600182e80"),"eul","eul_clock_inline",
               "Inline audio EUCLID step clock; stock waveforms bypass"),
        Detour(0x40003eec,H("202f0044d092"),"eul","eul_clock_midi",
               "MIDI EUCLID step clock before native cycle handling"),
        Detour(0x400572e8,H("4fefff8448d77cfc"),"eul","eul_ui_draw",
               "LFO SETUP drawer: Euclid editor or original page",pad_to=8),
        Detour(0x40055de0,H("4ab9400bc038"),"eul","eul_close",
               "Closing LFO SETUP also leaves its Euclid editor"),
        Detour(0x4004ab02,H("45f940020898"),"eul","eul_part_copy",
               "Part Reload copies the saved Euclid settings before native apply",kind="lea"),
        Detour(0x40029a7c,H("45f940020898"),"eul","eul_part_copy",
               "Part Paste/Undo copies Euclid settings before native apply",kind="lea"),
        Detour(0x40029358,H("701123c0460d0ffa"),"eul","eul_capture_clip",
               "Part clipboard mirror, after the shared native copy call",pad_to=8),
        Detour(0x4002931c,H("701123c0460c80f0"),"eul","eul_capture_undo",
               "Part undo mirror, after the shared native copy call",pad_to=8),
    ),
    symbol_refs=(
        SymbolRef(0x400bdf82,0,"eul","eul_icon","native WAVE 19 pictogram, replacing NULL padding"),
        SymbolRef(0x400d625c,0x400038bc,"eul","eul_audio","audio WAVE 19"),
        SymbolRef(0x400d62dc,0x400038bc,"eul","eul_midi","eul MIDI WAVE 19"),
        SymbolRef(0x400bbb56,0x4005cbc8,"eul","eul_ui_yes","YES opens Euclid or changes editor page"),
        SymbolRef(0x400bbb70,0x4005b99c,"eul","eul_ui_no","NO returns to native LFO setup"),
        *(SymbolRef(a,old,"eul","eul_ui_arrow","Euclid editor page navigation")
          for a,old in ((0x400bbaee,0x4003a3b4),(0x400bbb08,0x4003a3b4),
                        (0x400bbb22,0x400321d0),(0x400bbb3c,0x400321d0))),
        *(SymbolRef(0x400bbc74+22*i,0x40038e04,"eul","eul_ui_encoder",
                    "Euclid controls without native push acceleration") for i in range(7)),
    ),
    tables=(TableGrow("LFO WAVE labels",0x400be38e,19,(("eul","eul_label"),),
                      ((0x4003be5c,0x400be38e),)),),
    pokes=(Poke(0x400d38ac,H("00000013"),H("00000014"),"audio WAVE count 20"),
           Poke(0x400d4218,H("00000013"),H("00000014"),"MIDI WAVE count 20"),
           Poke(0x4003be50,H("7213"),H("7214"),"WAVE formatter accepts EUCLID")),
)
