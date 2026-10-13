    .text
    .global ap_encoder
/* Enter after the stock editor has saved its registers and loaded
 * d0=encoder (A=0, C=2, F=5, LEVEL=6), d5=delta. Other controls run stock.
 * This precedes MIDI SCALES' separate KEY hook at 0x4007a3e2.
 */
ap_encoder:
    tst.l %d0
    bne.s .ap_native
    move.l %d5,-(%sp)
    jsr ap_select
    addq.l #4,%sp
    jmp 0x4007a6ba
.ap_native:
    moveq #2,%d1
    cmp.l %d0,%d1
    bne.s .ap_other
    jmp 0x4007a304
.ap_other:
    jmp 0x4007a3e2
