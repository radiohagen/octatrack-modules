"""Opt-in integration with the pinned Synth Machine, without editing its submodule.

Unselected: returns the original assembly verbatim. Selected: three explicit
call sites and marker reset; no second claimant on any stock firmware hook.
A source hash and unique anchors make an upstream change fail closed.
"""
from pathlib import Path
import hashlib
ROOT=Path(__file__).resolve().parents[2]
PIN="2b1feb174f228dddfca028afe53b885261209d1f22d2e77f93ee883a07efeef8"
def assembly(modules):
    path=ROOT/"modules/synth/upstream/synth/poly.s"
    source=path.read_text()
    if "SOPHIE" not in modules:return source
    if hashlib.sha256(path.read_bytes()).hexdigest()!=PIN:
        raise ValueError("Sophie bridge needs review for this Synth upstream revision")
    def insert(anchor, replacement):
        nonlocal source
        if source.count(anchor)!=1:raise ValueError("Sophie bridge anchor drift: "+anchor)
        source=source.replace(anchor,replacement)
    insert("sy_cold:                                 |", "sy_cold:\n        jsr sf_begin_hook\n                                        |")
    insert("sy_no:\n", "sy_no:\n        lea sf_active,%a0\n        clr.b (%a0,%d2.l)\n")
    insert("        lea     16(%a2),%a1              | their first L long\n", "        lea     16(%a2),%a1              | their first L long\n        jsr sf_fill_hook\n        bne sy_done\n")
    insert("po_pg_have:\n        move.l  %a2,%d0\n", "po_pg_have:\n        move.l  %a2,%d0\n        jsr sf_page_hook\n")
    return source
