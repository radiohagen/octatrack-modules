"""Original two-oscillator Supersaw through the existing Synth transport."""
from remix.schema import Category, Gate, Kind, Linked, Module, Proof
MODULE = Module(
    name='supersaw', key='SUPERSAW', kind=Kind.CF_PATCH,
    category=Category.MACHINES, author='radiohagen',
    author_url='https://github.com/radiohagen/octatrack-modules',
    doc='Two detuned saws per note, morph, sub and drive on FMSYNTH-SUPERSAW marker tracks.',
    proof=Proof.CHECK, proof_note='experimental; hardware unqualified',
    requires=('SYNTH MACHINE',),
    linked=(Linked('supersaw', 'modules/supersaw/adapter.s', dram=True),
            Linked('supersawhooks', 'modules/supersaw/hooks.s', dram=True)),
    gates=(Gate('tools/verify/verify_supersaw.py', remix_arg=False),
           Gate('tools/verify/verify_supersaw_image.py', remix_arg=False, venv=True, stage='image')),
)
