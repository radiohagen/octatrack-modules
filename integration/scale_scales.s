/* SCALES catalogue adapter. Reads an explicit local context; consumers own
 * Follow resolution. Saved KEY uses SCALES' destination-Part ID semantics. */
    .text
    .global msp_scales_read
msp_scales_read:
    lea -24(%sp),%sp
    movem.l %d0-%d3/%a0-%a1,(%sp)
    cmpi.l #7,%d0
    bhi.w .invalid
    cmpi.l #127,%d1
    bhi.w .invalid
    cmpi.l #64,%d1
    bcc.s .saved
    jsr store_part_midi_key
    bra.s .decode
.saved:
    subi.l #64,%d1
    mulu.w #36,%d0
    addi.l #0x4e2+17,%d0
    jsr store_part_saved_read
    move.l 4(%sp),%d1
.decode:
    tst.l %d0
    bmi.s .invalid
    beq.s .done
    move.l (%sp),%d2
    jsr sc_decode_at
    tst.l %d0
    bmi.s .off
    move.l %d0,%d2
    lsr.l #4,%d0
    move.l %d0,-(%sp)
    jsr sc_mask
    move.l (%sp)+,%d1
    tst.l %d0
    beq.s .invalid
    andi.l #15,%d2
    lsl.l #8,%d2
    lsl.l #4,%d2
    or.l %d2,%d0
    cmpi.l #1,%d1
    beq.s .native
    cmpi.l #6,%d1
    bne.s .done
.native:
    ori.l #0x10000,%d0
    bra.s .done
.off:
    moveq #0,%d0
    bra.s .done
.invalid:
    moveq #-1,%d0
.done:
    movem.l 4(%sp),%d1-%d3/%a0-%a1
    lea 24(%sp),%sp
    rts
