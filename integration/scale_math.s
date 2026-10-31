/* Provider-independent descriptor operations; no Part/UI or output ownership.
 * Mask bits0..11, tonic bits12..15, stock-snap flag16, OFF=0.
 * Invalid descriptors suppress quantized pitches (-1), never approximate.
 * Harmony conversion accepts only the seven exact legacy mode masks. */
    .text
    .global msp_quant,msp_legacy
msp_quant:
    lea -24(%sp),%sp
    movem.l %d1-%d5/%a0,(%sp)
    move.l %d0,%d2
    cmpi.l #127,%d2
    bhi.w .quant_done
    tst.l %d1
    beq.w .quant_done
    cmpi.l #0x1ffff,%d1
    bhi.w .quant_bad
    move.l %d1,%d3
    lsr.l #8,%d3
    lsr.l #4,%d3
    andi.l #15,%d3
    cmpi.l #11,%d3
    bhi.w .quant_bad
    move.l %d1,%d4
    andi.l #0xfff,%d4
    beq.w .quant_bad
    btst #16,%d1
    beq.s .quant_nearest
    moveq #12,%d0
    cmpi.l #0xab5,%d4
    beq.s .quant_stock
    moveq #21,%d0
    cmpi.l #0x5ad,%d4
    bne.w .quant_bad
.quant_stock:
    sub.l %d3,%d0
    add.l %d2,%d0
.quant_mod:
    cmpi.l #12,%d0
    blt.s .quant_table
    subi.l #12,%d0
    bra.s .quant_mod
.quant_table:
    lea 0x400d80a0,%a0
    add.l (%a0,%d0.l*4),%d2
    bra.s .quant_done
.quant_nearest:
    moveq #0,%d5
.quant_search:
    move.l %d2,%d0
    sub.l %d5,%d0
    bmi.s .quant_upper
    bsr.s .quant_degree
    bne.s .quant_found
.quant_upper:
    move.l %d2,%d0
    add.l %d5,%d0
    cmpi.l #127,%d0
    bhi.s .quant_next
    bsr.s .quant_degree
    bne.s .quant_found
.quant_next:
    addq.l #1,%d5
    bra.s .quant_search
.quant_found:
    move.l %d0,%d2
    bra.s .quant_done
.quant_bad:
    moveq #-1,%d2
.quant_done:
    move.l %d2,%d0
    movem.l (%sp),%d1-%d5/%a0
    lea 24(%sp),%sp
    rts
.quant_degree:
    move.l %d0,%d1
    sub.l %d3,%d1
    bpl.s .degree_mod
    addi.l #12,%d1
.degree_mod:
    cmpi.l #12,%d1
    blt.s .degree_test
    subi.l #12,%d1
    bra.s .degree_mod
.degree_test:
    btst %d1,%d4
    rts

msp_legacy:
    lea -16(%sp),%sp
    movem.l %d1-%d3/%a0,(%sp)
    tst.l %d0
    beq.s .legacy_off
    cmpi.l #0x1ffff,%d0
    bhi.s .legacy_bad
    move.l %d0,%d1
    lsr.l #8,%d1
    lsr.l #4,%d1
    andi.l #15,%d1
    cmpi.l #11,%d1
    bhi.s .legacy_bad
    move.l %d0,%d2
    andi.l #0xfff,%d2
    btst #16,%d0
    beq.s .legacy_modes
    cmpi.l #0xab5,%d2
    beq.s .legacy_modes
    cmpi.l #0x5ad,%d2
    bne.s .legacy_bad
.legacy_modes:
    lea .legacy_masks,%a0
    moveq #0,%d3
.legacy_find:
    cmp.w (%a0,%d3.l*2),%d2
    beq.s .legacy_found
    addq.l #1,%d3
    cmpi.l #7,%d3
    bne.s .legacy_find
.legacy_bad:
    moveq #-2,%d0
    bra.s .legacy_done
.legacy_off:
    moveq #-1,%d0
    bra.s .legacy_done
.legacy_found:
    lsl.l #6,%d3
    lsl.l #2,%d1
    move.l %d3,%d0
    or.l %d1,%d0
.legacy_done:
    movem.l (%sp),%d1-%d3/%a0
    lea 16(%sp),%sp
    rts
    .balign 2
.legacy_masks: .word 0xab5,0x6ad,0x5ab,0xad5,0x6b5,0x5ad,0x56b
