"""Opt-in CPU Supersaw calls in the pinned Synth source.

The existing Synth owns native hooks. Unselected source is emitted verbatim.
Legacy Sophie composition is supported only when that separate source is present.
"""
from pathlib import Path
import hashlib
import runpy
ROOT = Path(__file__).resolve().parents[2]
PIN = "2b1feb174f228dddfca028afe53b885261209d1f22d2e77f93ee883a07efeef8"
def assembly(modules, remix=None):
    source = (ROOT/'modules/synth/upstream/synth/poly.s').read_text()
    if 'SOPHIE' in modules:
        source = runpy.run_path(str(ROOT/'modules/sophie/bridge.py'))['assembly'](modules)
    if 'SUPERSAW' not in modules:
        return source
    path = ROOT/'modules/synth/upstream/synth/poly.s'
    if hashlib.sha256(path.read_bytes()).hexdigest() != PIN:
        raise ValueError('Supersaw bridge needs review for this Synth revision')
    def insert(anchor, replacement):
        nonlocal source
        if source.count(anchor) != 1:
            raise ValueError('Supersaw bridge anchor drift: ' + anchor)
        source = source.replace(anchor, replacement)
    insert('\nsy_cold:', '\nsy_cold:\n        jsr ss_begin_hook')
    insert('sy_no:\n', 'sy_no:\n        lea ss_active,%a0\n        clr.b (%a0,%d2.l)\n')
    # A selected Sophie voice finishes before the Supersaw selector. Keep
    # its sample path unchanged; ordinary FM and Supersaw continue below.
    anchor = ('        jsr sf_fill_hook\n        bne sy_done\n'
              if 'SOPHIE' in modules else
              '        lea     16(%a2),%a1              | their first L long\n')
    insert(anchor, anchor +
           '        lea ss_active,%a0\n        tst.b (%a0,%d2.l)\n'
           '        beq ss_not_selected\n        jsr ss_fill_hook\n        bne sy_done\nss_not_selected:\n')
    if 'SOPHIE' in modules:
        insert('        jsr sf_fill_hook\n        bne sy_done\n',
               '        lea sf_active,%a0\n        tst.b (%a0,%d2.l)\n'
               '        beq ss_after_sophie\n        jsr sf_fill_hook\n        bne sy_done\nss_after_sophie:\n')
    # Adapted mono voices use native pitch and AMP, but not FM ratio,
    # feedback or index envelopes. Avoid calculating those every frame.
    select = '        lea ss_active,%a0\n        tst.b (%a0,%d2.l)\n        bne ss_amp_frame\n'
    if 'SOPHIE' in modules:
        select += '        lea sf_active,%a0\n        tst.b (%a0,%d2.l)\n        bne ss_amp_frame\n'
    insert('        move.l  %d0,S_INC(%a3)           | carrier increment: the true pitch\n',
           '        move.l  %d0,S_INC(%a3)           | carrier increment: the true pitch\n'+select)
    insert('        move.l  52(%sp),%d2              | track (d2 was RTIM above)\n',
           'ss_amp_frame:\n        move.l  52(%sp),%d2              | track (d2 was RTIM above)\n')
    insert('po_pg_have:\n        move.l  %a2,%d0\n',
           'po_pg_have:\n        move.l  %a2,%d0\n        jsr ss_page_hook\n')
    # Pinned native pool, allocation and envelopes; no second note allocator.
    insert('po_ca_g:\n', 'po_ca_g:\n        jsr ss_carry_hook\n')
    insert('        move.l  %d0,V_INC(%a6)\n',
           '        move.l  %d0,V_INC(%a6)\n'
           '        lea ss_active,%a0\n        tst.b (%a0,%d2.l)\n'
           '        bne ss_poly_amp\n')
    insert('        move.l  V_HOLD(%a6),%d0          | a gated sequencer note:',
           'ss_poly_amp:\n        move.l  V_HOLD(%a6),%d0          | a gated sequencer note:')
    source += '\n        .global ss_native_voices\n        .set ss_native_voices,po_voices\n'
    return source
