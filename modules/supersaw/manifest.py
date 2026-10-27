"""Original two-oscillator Supersaw through the existing Synth transport."""
from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof
MODULE = Module(
    name='supersaw', key='SUPERSAW', kind=Kind.CF_PATCH,
    category=Category.MACHINES, author='radiohagen',
    author_url='https://github.com/radiohagen/octatrack-modules',
    doc='Two detuned saws per note, morph, sub and drive on FMSYNTH-SUPERSAW marker tracks.',
    proof=Proof.CHECK, proof_note='experimental; hardware unqualified',
    requires=('SYNTH MACHINE',),
    linked=(Linked('supersaw', 'modules/supersaw/adapter.s', dram=True),
            Linked('supersawhooks', 'modules/supersaw/hooks.s', dram=True)),
    detours=(
        Detour(0x4003bff0,bytes.fromhex('711041f9400d5f38'),'supersawhooks','ss_lfo_names_hook', 'Supersaw LFO PLAYBACK destination names; native fallback'),
        Detour(0x4003c8d4,bytes.fromhex('2f5000404fef0010'),'supersawhooks','ss_setup_draw_hook', 'Supersaw setup descriptor; other rows untouched',pad_to=8),
        Detour(0x4003cd98,bytes.fromhex('2e06e78fdc869e86'),'supersawhooks','ss_setup_storage_hook', 'Supersaw setup values from retained unused machine row',pad_to=8),
        Detour(0x4003a474,bytes.fromhex('4fefffe048d73c3c'),'supersawhooks','ss_setup_edit_hook', 'Supersaw setup editor; native fallback',pad_to=8),
        Detour(0x40002318,bytes.fromhex('4fefffa048d77cfc'),'supersawhooks','ss_validate_hook', 'Preserve tagged Supersaw setup through native Part validation',pad_to=8),
    ),
    gates=(Gate('tools/verify/verify_supersaw.py', remix_arg=False),
           Gate('tools/verify/verify_supersaw_image.py', remix_arg=False, venv=True, stage='image')),
)
