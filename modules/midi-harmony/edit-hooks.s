    .include "remix.inc"
    .text
    .global hd_memcpy,hd_step_copy,hd_step_apply
/* Compatibility entry points route through the system, not another client. */
    .global ch_memcpy,mh_ed_copy_pre,mh_ed_copy_post
ch_memcpy:
hd_memcpy:
    jmp ed_copy
/* d0/d1/d2 = destination/source/length. Save native ABI arguments because
 * the generated C helpers may reuse their incoming argument slots. */
mh_ed_copy_pre:
    lea -12(%sp),%sp
    movem.l %d0-%d2,(%sp)
    move.l %d2,-(%sp)
    move.l %d1,-(%sp)
    move.l %d0,-(%sp)
    jsr ch_copy_mirror
    movem.l 12(%sp),%d0-%d2
    movem.l %d0-%d2,(%sp)
    jsr hd_copy_before_c
    lea 24(%sp),%sp
    rts
mh_ed_copy_post:
    jsr hd_copy_after_c
    tst.l %d0
    bmi.s .copy_done
    moveq #0,%d1
    move.b 0x80000002,%d1
    cmp.l %d1,%d0
    bne.s .copy_done
    jsr ch_nv_save
.copy_done:
    rts
hd_step_copy: /* ordinary five-argument step-copy ABI, all registers kept */
    lea -16(%sp),%sp
    movem.l %d0-%d1/%a0-%a1,(%sp)
    move.l 40(%sp),-(%sp) /* extra return address from ch_step_copy */
    move.l 40(%sp),-(%sp)
    move.l 40(%sp),-(%sp)
    move.l 40(%sp),-(%sp)
    move.l 40(%sp),-(%sp)
    jsr hd_step_copy_c
    lea 20(%sp),%sp
    movem.l (%sp),%d0-%d1/%a0-%a1
    lea 16(%sp),%sp
    rts
/* After the native 32-byte root/lock record has reached bank and CS1. */
hd_step_apply:
    lea -16(%sp),%sp
    movem.l %d0-%d1/%a0-%a1,(%sp)
    move.l %d4,-(%sp)
    move.l 120(%sp),-(%sp) /* original sp+100 track */
    move.l 120(%sp),-(%sp) /* original sp+96 pattern */
    move.l %d3,-(%sp)
    move.l %a5,-(%sp)
    jsr hd_step_paste_c
    lea 20(%sp),%sp
    tst.l %d0
    bmi.s .step_done
    moveq #0,%d1
    move.b 0x80000002,%d1
    cmp.l %d1,%d0
    bne.s .step_done
    jsr ch_nv_save
.step_done:
    movem.l (%sp),%d0-%d1/%a0-%a1
    lea 16(%sp),%sp
    move.b #1,%d0
    lsl.l %d3,%d0
    jmp 0x4002c772
