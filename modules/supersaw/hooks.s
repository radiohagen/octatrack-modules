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
        move.l 48(%a1),-(%sp)
        move.l %d0,-(%sp)
        move.l %d2,-(%sp)
        jsr ss_carry
        lea 12(%sp),%sp
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea 16(%sp),%sp
        rts

        .global ss_fine_hook, ss_setup_draw_hook, ss_setup_storage_hook
        .global ss_setup_edit_hook, ss_validate_hook, ss_stock_validate
ss_fine_hook:
        lea -12(%sp),%sp
        movem.l %d1/%a0-%a1,(%sp)
        move.l %d0,-(%sp)
        move.l %d2,-(%sp)
        jsr ss_fine
        addq.l #8,%sp
        movem.l (%sp),%d1/%a0-%a1
        lea 12(%sp),%sp
        rts
ss_setup_draw_hook:
        lea -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        move.l %d6,-(%sp)
        move.l %d5,-(%sp)
        move.l (%a0),-(%sp)
        jsr ss_setup_page
        lea 12(%sp),%sp
        move.l %d0,80(%sp)
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea 32(%sp),%sp
        jmp 0x4003c8dc
ss_setup_storage_hook:
        lea -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        move.l %d5,-(%sp)
        move.l %d6,-(%sp)
        jsr ss_setup_row
        addq.l #8,%sp
        move.l %d0,%d6
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea 16(%sp),%sp
        move.l %d6,%d7
        lsl.l #3,%d7
        add.l %d6,%d6
        sub.l %d6,%d7
        jmp 0x4003cda0
ss_setup_edit_hook:
        lea -32(%sp),%sp
        movem.l %d2-%d5/%a2-%a5,(%sp)
        move.l 40(%sp),-(%sp)
        move.l 40(%sp),-(%sp)
        jsr ss_setup_edit
        addq.l #8,%sp
        tst.l %d0
        bne ss_setup_edited
        jmp 0x4003a47c
ss_setup_edited:
        jmp 0x4003a624
ss_validate_hook:
        jmp ss_validate
ss_stock_validate:
        lea -96(%sp),%sp
        movem.l %d2-%d7/%a2-%fp,(%sp)
        jmp 0x40002320

        .global ss_lfo_page_hook
ss_lfo_page_hook:
        lea -12(%sp),%sp
        movem.l %d1/%a0-%a1,(%sp)
        move.l %d3,-(%sp)
        move.l %d0,-(%sp)
        jsr ss_lfo_page
        addq.l #8,%sp
        movem.l (%sp),%d1/%a0-%a1
        lea 12(%sp),%sp
        rts
