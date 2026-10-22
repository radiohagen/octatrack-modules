"""Sophie FUSE POC through the existing Synth Machine source transport."""
from remix.schema import Category, Gate, Kind, Linked, Module, Proof
MODULE=Module(
 name="sophie",key="SOPHIE",kind=Kind.CF_PATCH,
 category=Category.MACHINES,author="soejrd; Octatrack adapter: mattiaswolff",
 author_url="https://github.com/soejrd/digisophie",
 doc="Sophie FUSE mono percussion on FMSYNTH-SOPHIE marker tracks; existing FM and bus effects retained.",
 proof=Proof.CHECK,proof_note="experimental POC; no physical hardware qualification",
 requires=("SYNTH MACHINE",),
 linked=(Linked("sophie", "modules/sophie/adapter.s",dram=True),
         Linked("sophiehooks", "modules/sophie/hooks.s",dram=True)),
 gates=(Gate("tools/verify/verify_sophie.py",remix_arg=False),
        Gate("tools/verify/verify_sophie_image.py",remix_arg=False,venv=True,stage="image")),
)
