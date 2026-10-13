| SPDX-License-Identifier: MIT
| Synth register ABI adapters. C uses integer multiplies; EMAC untouched.
        .text
        .global ss_begin_hook, ss_fill_hook, ss_page_hook
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
        move.l %d7,-(%sp)
        move.l %a1,-(%sp)
        move.l 0x800062a8,-(%sp)
        move.l %a3,-(%sp)
        move.l %d2,-(%sp)
        jsr ss_fill
        lea 20(%sp),%sp
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
