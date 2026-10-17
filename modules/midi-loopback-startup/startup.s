/* Silent DSP-upload entry sequence, derived from sanderlegit's BOOT TRACE.
 * The call/stack access order and footprint are deliberately preserved from
 * the hardware-tested image. Cause is open; this is an empirical workaround.
 * No UART access, allocated state, or normal MIDI-path work is introduced.
 */
        .text
        .global startup_trace,startup_upload
startup_trace:
        move.l %d1,-(%sp)
        moveq #0x7f,%d1
        bsr.s startup_values
        move.l (%sp)+,%d1
        rts
startup_values:
        lea (-16,%sp),%sp
        movem.l %d0-%d3,(%sp)
        move.l %d1,%d3
        move.l #0x90,%d1
        bsr.s startup_return
        move.l (%sp),%d1
        bsr.s startup_return
        move.l %d3,%d1
        andi.l #0x7f,%d1
        bsr.s startup_return
        movem.l (%sp),%d0-%d3
        lea (16,%sp),%sp
        rts
startup_return:
        rts
        nop
        nop
        .org 0x52,0
startup_upload:
        nop
        bsr.w startup_trace
        clr.b %d0
        move.b %d0,(0xfc0a400c).l
        jmp (0x40001e58).l
/* Preserve image placement and compression of the tested composition. */
        .org 848,0
