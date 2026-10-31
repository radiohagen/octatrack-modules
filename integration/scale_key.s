/* Stock/MIDI Scales adapter. This unit reads a local explicit Part only;
 * clients own route resolution. No settings, hooks or persisted data change. */
    .include "remix.inc"
    .text
    .global msp_key_read
msp_key_read:
    lea -20(%sp),%sp
    movem.l %d1-%d4/%a0,(%sp)
    cmpi.l #7,%d0
    bhi.w .read_bad
    cmpi.l #127,%d1
    bhi.w .read_bad
    cmpi.l #64,%d1
    bcc.s .read_saved
    jsr store_part_midi_key
    bra.s .read_decode
.read_saved:
    move.l %d0,%d2
    mulu.w #36,%d2
    subi.l #64,%d1
    move.l %d1,%d3
    andi.l #3,%d3
    mulu.w #0x18b2,%d3
    add.l %d3,%d2
    lsr.l #2,%d1
    move.l #0x9b340,%d4
    mulu.l %d4,%d1
    add.l %d1,%d2
    lea 0x400e21e0+0x9504a+0x4e2+17,%a0 /* bank 0 + saved Parts + setup KEY */
    moveq #0,%d0
    move.b (%a0,%d2.l),%d0
.read_decode:
    tst.l %d0
    bmi.s .read_bad
    beq.s .read_done
    .if SCALE_KEY_EXTENDED
    cmpi.l #84,%d0
    .else
    cmpi.l #24,%d0
    .endif
    bhi.s .read_off
    move.l %d0,%d4
    subq.l #1,%d0
    lea .key_modes,%a0
    moveq #0,%d2
    move.w (%a0,%d0.l*2),%d2 /* mode<<6 | tonic<<2 */
    move.l %d2,%d3
    lsr.l #6,%d2
    lsr.l #2,%d3
    andi.l #15,%d3
    lsl.l #8,%d3
    lsl.l #4,%d3
    lea .key_masks,%a0
    moveq #0,%d0
    move.w (%a0,%d2.l*2),%d0
    or.l %d3,%d0
    cmpi.l #24,%d4
    bhi.s .read_done
    ori.l #0x10000,%d0
    bra.s .read_done
.read_off:
    moveq #0,%d0
    bra.s .read_done
.read_bad:
    moveq #-1,%d0
.read_done:
    movem.l (%sp),%d1-%d4/%a0
    lea 20(%sp),%sp
    rts
    .balign 2
.key_masks: .word 0xab5,0x6ad,0x5ab,0xad5,0x6b5,0x5ad,0x56b
.key_modes:
    .set .tonic,0
    .rept 12
    .word .tonic*4,320+.tonic*4
    .set .tonic,.tonic+1
    .endr
    .set .tonic,0
    .rept 12
    .word 64+.tonic*4,128+.tonic*4,192+.tonic*4
    .word 256+.tonic*4,384+.tonic*4
    .set .tonic,.tonic+1
    .endr
