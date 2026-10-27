"""Opt-in CPU Supersaw calls in the pinned Synth source.

The existing Synth owns native hooks. Unselected source is emitted verbatim.
Legacy Sophie composition is supported only when that separate source is present.
"""
from pathlib import Path
import hashlib
import os
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
    # The per-voice FM calculation is already bypassed below. Its per-track
    # ratio/feedback/index/decay preparation is equally unused by Supersaw.
    insert('po_fr_params:\n', 'po_fr_params:\n'
           '        lea ss_active,%a0\n        tst.b (%a0,%d2.l)\n'
           '        bne ss_poly_amp_params\n')
    insert('        move.l  #CV_STRIDE,%d0           | AMP REL -> the release k (po_relk: the DSP\'s law, plan B)\n',
           'ss_poly_amp_params:\n'
           '        move.l  #CV_STRIDE,%d0           | AMP REL -> the release k (po_relk: the DSP\'s law, plan B)\n')
    # Voice capacity must not attenuate a Supersaw note. Native FM keeps
    # its equal-power cap; Supersaw sums in int32 and saturates only once.
    insert('        move.l  %d0,T_GMAX(%a5)          | and po_fill\'s limiter holds the sum at FS (in phase it reaches 2.0 FS at 4)\n',
           '        lea ss_active,%a0\n        tst.b (%a0,%d2.l)\n'
           '        beq ss_native_gmax\n        move.l #32767,%d0\n'
           'ss_native_gmax:\n        move.l %d0,T_GMAX(%a5)\n')
    insert('        move.l  %d0,V_INC(%a6)\n',
           '        move.l  %d0,V_INC(%a6)\n'
           '        lea ss_active,%a0\n        tst.b (%a0,%d2.l)\n'
           '        bne ss_poly_amp\n')
    insert('        move.l  V_HOLD(%a6),%d0          | a gated sequencer note:',
           'ss_poly_amp:\n        move.l  V_HOLD(%a6),%d0          | a gated sequencer note:')
    insert('        mvz.w   6(%a4),%d0\n        subi.l  #0x4000,%d0',
           '        mvz.w   6(%a4),%d0\n        jsr ss_fine_hook\n        subi.l  #0x4000,%d0')
    insert('po_lp_have:\n        move.l  %a1,%d0\n',
           'po_lp_have:\n        move.l  %a1,%d0\n        jsr ss_lfo_page_hook\n')
    insert('po_keyrec:\n', 'po_keyrec:\n        lea ss_active,%a0\n        tst.b (%a0,%d2.l)\n        beq ss_record_native\n        moveq #0,%d0\n        rts\nss_record_native:\n')
    # po_rate_fold forces RATE=1.0: its output depends only on the final
    # slewed pitch word and the immutable stock pitch table. A small exact
    # cache serves held notes and repeated chord pitches across all tracks.
    # Keep the native path for every other synth. Collisions only cost a miss.
    for comment in ('the increment for the word d6, any octave',
                    'the increment, the word folded by octaves'):
        anchor = '        bsr     po_rate_fold             | d0 = ' + comment
        insert(anchor, '        bsr     ss_pitch_rate            | d0 = ' + comment)
    source += r"""
        .text
ss_pitch_rate:
        lea ss_active,%a0
        tst.b (%a0,%d2.l)
        beq po_rate_fold
        move.l %d6,%d0
        asr.l #8,%d0
        andi.l #31,%d0
        move.l %d0,%d1
        add.l %d0,%d0
        add.l %d1,%d0
        lsl.l #2,%d0
        lea ss_pitch_cache,%a0
        adda.l %d0,%a0
        tst.l 8(%a0)
        beq ss_pitch_miss
        cmp.l (%a0),%d6
        bne ss_pitch_miss
        move.l 4(%a0),%d0
        rts
ss_pitch_miss:
        move.l %a0,-(%sp)
        bsr po_rate_fold
        move.l (%sp)+,%a0
        move.l %d6,(%a0)
        move.l %d0,4(%a0)
        moveq #1,%d1
        move.l %d1,8(%a0)
        rts
        .data
        .align 4
        .global ss_pitch_cache
ss_pitch_cache:
        .rept 32
        .long 0,0,0
        .endr
        .text
"""
    if os.environ.get('SS_DIAGNOSTICS') == '1':
        # Optional, bounded observation. Separate MIDI/audio rings avoid
        # publication races when the frame interrupt preempts MIDI input.
        insert('po_mon_start:\n', 'po_mon_start:\n        bsr ss_diag_enqueue_hook\n')
        insert('        bmi     po_moff_stock\n',
               '        bmi     po_moff_stock\n        bsr ss_diag_off_hook\n')
        insert('po_start1:\n', 'po_start1:\n        bsr ss_diag_activate_hook\n')
        insert('        bsr     po_start\n', '        bsr     ss_diag_allocator\n')
        for name, kind, note in (('enqueue',1,'        mvz.b (%a3),%d0'),
                                 ('off',2,'        mvz.b (%a3),%d0'),
                                 ('activate',3,'        move.l %d7,%d0'),
                                 ('alloc_begin',4,'        moveq #0,%d0'),
                                 ('alloc_end',5,'        moveq #0,%d0')):
            source += f"""
ss_diag_{name}_hook:
        lea -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
{note}
        move.l %d0,-(%sp)
        move.l #{kind},-(%sp)
        move.l %d2,-(%sp)
        jsr ss_diag_event
        lea 12(%sp),%sp
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea 16(%sp),%sp
        rts
"""
        source += """
ss_diag_allocator:
        bsr ss_diag_alloc_begin_hook
        bsr po_start
        bra ss_diag_alloc_end_hook
        .global ss_native_state, ss_native_clock
        .set ss_native_state,sy_state
        .set ss_native_clock,po_clock
"""
    source += '\n        .global ss_native_voices\n        .set ss_native_voices,po_voices\n'
    return source
