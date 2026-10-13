"""OCTABAM84 selection plus the optional Sophie proof of concept."""
from dataclasses import replace
from pathlib import Path
import runpy
from remix.schema import Proof
base=runpy.run_path(str(Path(__file__).resolve().parents[1]/"mattias-bottleservice/remix.py"))["REMIX"]
REMIX=replace(base,name="mattias-sophie-poc",modules=base.modules+("SOPHIE",),
 family="probes",proof=Proof.CHECK,proof_note="one mono FUSE track verified with FM and bus hosts in the emulator; hardware unqualified",
 doc="Complete Mattias BottleService selection plus Sophie FUSE percussion.")
