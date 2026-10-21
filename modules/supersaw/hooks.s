| SPDX-License-Identifier: MIT
| Synth register ABI adapters. C uses integer multiplies; EMAC untouched.
        .text
        .global ss_begin_hook, ss_fill_hook, ss_page_hook, ss_carry_hook
ss_begin_hook:
        lea -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        move.l %a3,-(%sp)
        move.l %d2,-(%sp)
        jsr ss_begin
        addq.l #8,%sp
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea 16(%sp),%sp
        rts
ss_fill_hook:
        lea -12(%sp),%sp
        movem.l %d1/%a0-%a1,(%sp)
        lea ss_native_voices,%a0
        move.l %d2,%d0
        lsl.l #8,%d0
        add.l %d0,%a0
        move.l %a0,-(%sp)
        move.l %d7,-(%sp)
        move.l %a1,-(%sp)
        move.l 0x800062a8,-(%sp)
        move.l %a3,-(%sp)
        move.l %d2,-(%sp)
        jsr ss_track_fill
        lea 24(%sp),%sp
        movem.l (%sp),%d1/%a0-%a1
        lea 12(%sp),%sp
        tst.l %d0
        rts
ss_page_hook:
        lea -12(%sp),%sp
        movem.l %d1/%a0-%a1,(%sp)
        move.l %d3,-(%sp)
        move.l %d0,-(%sp)
        jsr ss_page
        addq.l #8,%sp
        movem.l (%sp),%d1/%a0-%a1
        lea 12(%sp),%sp
        rts

ss_carry_hook:
        lea -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        lea ss_native_voices,%a0
        move.l %a1,%d0
        sub.l %a0,%d0
        lsr.l #6,%d0
        andi.l #3,%d0
        move.l %d0,-(%sp)
        move.l %d2,-(%sp)
        jsr ss_carry
        addq.l #8,%sp
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea 16(%sp),%sp
        rts
