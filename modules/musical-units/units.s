| MUSICAL UNITS: display-only, no writes to parameter/project/engine state.
| Stock formatter ABI: fmt(char *buffer, int raw). Six bytes suffice for
| every result (five visible ASCII characters and NUL), as native cells do.
| Shared mu_beats ABI: a0=buffer, d0=numerator, d1=denominator in quarter
| notes. Numerator <=2048, denominator 1..65535. Tempo comes from the engine.
| Preserves
| d2-d7/a2-a6. Exact note names only; no tolerance or snapping.
        .text
        .global mu_beats,mu_milliseconds,mu_delay

        .macro LFO_ENTRY name,index,base,stride
        .global \name
\name:
        move.l  #\base,%a1
        moveq   #\stride,%d0
        .if \index < 0
        move.l  0x460d1a32,%d1
        .else
        moveq   #\index,%d1
        .endif
        bra.w   mu_lfo
        .endm

        LFO_ENTRY mu_audio_one,0,0x8f08a,30
        LFO_ENTRY mu_audio_two,1,0x8f08a,30
        LFO_ENTRY mu_audio_three,2,0x8f08a,30
        LFO_ENTRY mu_audio_setup,-1,0x8f08a,30
        LFO_ENTRY mu_midi_one,0,0x8f280,36
        LFO_ENTRY mu_midi_two,1,0x8f280,36
        LFO_ENTRY mu_midi_three,2,0x8f280,36
        LFO_ENTRY mu_midi_setup,-1,0x8f280,36

mu_lfo:
        lea     -12(%sp),%sp
        movem.l %d2-%d3/%a2,(%sp)
        move.l  20(%sp),%d2             | raw SPD being drawn (including held locks)
        move.l  16(%sp),%a2
        tst.l   %d2
        beq.w   mu_lfo_stop
        cmp.l   #127,%d2
        bhi.w   mu_lfo_unknown
        cmp.l   #2,%d1
        bhi.w   mu_lfo_unknown
        mvz.b   0x100b14cc,%d3          | same track/Part as stock's UI resolver
        cmp.l   #7,%d3
        bhi.w   mu_lfo_unknown
        mulu.l  %d0,%d3
        adda.l  %d3,%a1
        adda.l  %d1,%a1
        mvz.b   0x100b14cf,%d3
        cmp.l   #3,%d3
        bhi.w   mu_lfo_unknown
        move.l  #6322,%d0
        mulu.l  %d0,%d3
        adda.l  %d3,%a1
        move.l  0x46c82456,%d0
        beq.w   mu_lfo_unknown
        adda.l  %d0,%a1
        mvz.b   (%a1),%d1
        cmp.l   #6,%d1
        bhi.w   mu_lfo_unknown
        lsl.l   %d1,%d2
        move.l  %d2,%d1
        move.l  #512,%d0
        move.l  %a2,%a0
        bsr.w   mu_beats
        bra.s   mu_lfo_done
mu_lfo_stop:
        move.l  #0x53544f50,(%a2)       | STOP; SPD zero does not disable depth
        clr.b   4(%a2)
        bra.s   mu_lfo_done
mu_lfo_unknown:
        move.b  #63,(%a2)
        clr.b   1(%a2)
mu_lfo_done:
        movem.l (%sp),%d2-%d3/%a2
        lea     12(%sp),%sp
        rts

| Echo Freeze TIME: raw+1 in 1/128 notes, hence (raw+1)/32 beats.
| Unsynced retains its native numeric display until that mapping is proven.
mu_delay:
        lea     -12(%sp),%sp
        movem.l %d2-%d3/%a2,(%sp)
        move.l  16(%sp),%a2
        mvz.b   0x100b14cc,%d0
        moveq   #30,%d1
        mulu.l  %d1,%d0
        mvz.b   0x100b14cf,%d1
        move.l  #6322,%d2
        mulu.l  %d2,%d1
        add.l   %d1,%d0
        add.l   #0x8f087,%d0            | FX2 setup SYNC (slot 9)
        move.l  0x46c82456,%a0
        tst.l   %a0
        beq.s   mu_delay_native
        adda.l  %d0,%a0
        tst.b   (%a0)
        beq.s   mu_delay_native
        move.l  20(%sp),%d0
        addq.l  #1,%d0
        move.l  0x8000181c,%d1
        move.l  #128,%d2
        mulu.l  %d1,%d2
        move.l  #1440,%d3
        mulu.l  %d0,%d3
        cmp.l   %d2,%d3
        bhi.s   mu_delay_cap
        moveq   #32,%d1
        move.l  %a2,%a0
        bsr.w   mu_beats
        bra.s   mu_delay_done
mu_delay_cap:
        move.l  #0x34730000,(%a2)       | 4s: physical buffer limit
mu_delay_done:
        movem.l (%sp),%d2-%d3/%a2
        lea     12(%sp),%sp
        rts
mu_delay_native:
        movem.l (%sp),%d2-%d3/%a2
        lea     12(%sp),%sp
        jmp     0x4003c718

| MIDI LEN/NLEN: the note-off scheduler stores raw * 4 fine ticks
| (0x4009fd58..6c), 96 per quarter. Retain native zero/INF sentinels.
        .global mu_note_length,mu_arp_speed,mu_record_fade,mu_retrig,mu_transpose
mu_note_length:
        move.l  4(%sp),%a0
        move.l  8(%sp),%d0
        cmp.l   #127,%d0
        bhi.w   mu_adapter_unknown
        beq.s   mu_note_infinite
        tst.l   %d0
        bne.s   mu_note_duration
        move.w  #0x3000,(%a0)
        rts
mu_note_infinite:
        move.l  #0x494e4600,(%a0)
        rts
mu_note_duration:
        moveq   #24,%d1
        bra.w   mu_beats

| ARP SPD: native display raw+1, six MIDI clocks = a sixteenth.
mu_arp_speed:
        move.l  4(%sp),%a0
        move.l  8(%sp),%d0
        cmp.l   #95,%d0
        bhi.w   mu_adapter_unknown
        addq.l  #1,%d0
        bra.s   mu_note_duration

| Recorder FIN/FOUT: native ladder is in 1/16 of a sequencer step.
| Read the stock engine table rather than duplicate its firmware data.
mu_record_fade:
        move.l  4(%sp),%a0
        move.l  8(%sp),%d0
        cmp.l   #112,%d0
        bhi.w   mu_adapter_unknown
        lea     0x400ab63a,%a1
        move.l  (%a1,%d0.l*4),%d0
        move.l  #992250,%d1
        divu.l  %d1,%d0
        moveq   #64,%d1
        bra.w   mu_beats

| STATIC/FLEX RTIM: powers of two occur at raw 7 + 12*k.
| The interpolated engine table (0x40004084) has four entries per raw
| encoder value. Its values / 1016064000 are quarter notes: the
| engine advances its counter by tempo24 << 4 per sample.
mu_retrig:
        move.l  4(%sp),%a0
        move.l  8(%sp),%d0
        cmp.l   #127,%d0
        bhi.w   mu_adapter_unknown
        move.l  %d0,%d1
        subq.l  #7,%d1
        bcs.s   mu_retrig_time
        move.l  %d2,-(%sp)
        moveq   #1,%d2
mu_retrig_power:
        tst.l   %d1
        beq.s   mu_retrig_exact
        sub.l   #12,%d1
        bcs.s   mu_retrig_other
        add.l   %d2,%d2
        bra.s   mu_retrig_power
mu_retrig_exact:
        move.l  %d2,%d0
        move.l  (%sp)+,%d2
        move.l  #512,%d1
        bra.w   mu_beats
mu_retrig_other:
        move.l  (%sp)+,%d2
mu_retrig_time:
        lea     -12(%sp),%sp
        movem.l %d2-%d4,(%sp)
        lsl.l   #4,%d0
        lea     0x400aae0c,%a1
        move.l  (%a1,%d0.l),%d2
        move.l  0x8000181c,%d1
        cmp.l   #720,%d1
        bcs.s   mu_retrig_bad_tempo
        cmp.l   #7200,%d1
        bhi.s   mu_retrig_bad_tempo
        move.l  #7056,%d0
        mulu.l  %d0,%d1
| Rounded table * 10 / (7056 * tempo24), avoiding a 32-bit overflow.
        move.l  %d2,%d3
        divu.l  %d1,%d3
        move.l  %d3,%d4
        mulu.l  %d1,%d4
        sub.l   %d4,%d2
        moveq   #10,%d0
        mulu.l  %d0,%d3
        mulu.l  %d0,%d2
        move.l  %d1,%d4
        lsr.l   #1,%d4
        add.l   %d4,%d2
        divu.l  %d1,%d2
        move.l  %d3,%d0
        add.l   %d2,%d0
        movem.l (%sp),%d2-%d4
        lea     12(%sp),%sp
        bra.w   mu_milliseconds
mu_retrig_bad_tempo:
        movem.l (%sp),%d2-%d4
        lea     12(%sp),%sp
mu_adapter_unknown:
        move.b  #63,(%a0)
        clr.b   1(%a0)
        rts

| ARP TRAN: signed chromatic semitones; the native range remains -64..63.
mu_transpose:
        move.l  4(%sp),%a0
        move.l  8(%sp),%d0
        cmp.l   #127,%d0
        bhi.s   mu_adapter_unknown
        sub.l   #64,%d0
        move.l  %d0,-(%sp)
        pea     mu_fmt_semitones(%pc)
        move.l  %a0,-(%sp)
        jsr     0x40013a08
        lea     12(%sp),%sp
        rts
mu_fmt_semitones:
        .asciz "%dst"
        .balign 2

mu_beats:
        lea     -28(%sp),%sp
        movem.l %d2-%d7/%a2,(%sp)
        move.l  %a0,%a2
        move.l  %d0,%d2
        move.l  %d1,%d3
        tst.l   %d3
        beq.w   mu_beats_unknown
        cmp.l   #2048,%d2
        bhi.w   mu_beats_unknown
        cmp.l   #65535,%d3
        bhi.w   mu_beats_unknown
        lea     mu_note_table(%pc),%a1
        moveq   #MU_NOTE_COUNT-1,%d7
mu_note_loop:
        move.l  %d2,%d4
        moveq   #0,%d5
        move.w  2(%a1),%d5
        mulu.l  %d5,%d4
        moveq   #0,%d5
        move.w  (%a1),%d5
        mulu.l  %d3,%d5
        cmp.l   %d4,%d5
        beq.w   mu_note_found
        lea     10(%a1),%a1
        subq.l  #1,%d7
        bpl.s   mu_note_loop

| Convert quarter notes to rounded milliseconds using the live tempo24.
| Bounds above keep both products and the rounding addition within 32 bits.
        move.l  0x8000181c,%d4
        cmp.l   #720,%d4
        bcs.w   mu_beats_unknown
        cmp.l   #7200,%d4
        bhi.w   mu_beats_unknown
        mulu.l  %d3,%d4
        move.l  %d4,%d6
        lsr.l   #1,%d6
        move.l  #1440000,%d5
        mulu.l  %d2,%d5
        add.l   %d6,%d5
        divu.l  %d4,%d5
        bra.s   mu_time_format

| Shared physical-duration helper: a0=buffer, d0=unsigned milliseconds.
| Same preserved registers and six-byte output as mu_beats.
mu_milliseconds:
        lea     -28(%sp),%sp
        movem.l %d2-%d7/%a2,(%sp)
        move.l  %a0,%a2
        move.l  %d0,%d5
mu_time_format:
        cmp.l   #9999000,%d5
        bhi.w   mu_beats_unknown
        cmp.l   #1000,%d5
        bcc.s   mu_seconds
        lea     mu_fmt_milli(%pc),%a1
        bra.s   mu_print_one
mu_seconds:
        move.l  %d5,%d2
        moveq   #10,%d0
        addq.l  #5,%d5
        divu.l  %d0,%d5
        cmp.l   #1000,%d5
        bcc.s   mu_deci
        moveq   #100,%d0
        move.l  %d5,%d4
        divu.l  %d0,%d4
        mulu.l  %d4,%d0
        sub.l   %d0,%d5
        lea     mu_fmt_centi(%pc),%a1
        bra.s   mu_print_two
mu_deci:
        move.l  %d2,%d5
        add.l   #50,%d5
        moveq   #100,%d0
        divu.l  %d0,%d5
        cmp.l   #1000,%d5
        bcc.s   mu_integer
        moveq   #10,%d0
        move.l  %d5,%d4
        divu.l  %d0,%d4
        mulu.l  %d4,%d0
        sub.l   %d0,%d5
        lea     mu_fmt_deci(%pc),%a1
        bra.s   mu_print_two
mu_integer:
        move.l  %d2,%d5
        add.l   #500,%d5
        move.l  #1000,%d0
        divu.l  %d0,%d5
        lea     mu_fmt_integer(%pc),%a1
mu_print_one:
        move.l  %d5,-(%sp)
        move.l  %a1,-(%sp)
        move.l  %a2,-(%sp)
        jsr     0x40013a08
        lea     12(%sp),%sp
        bra.s   mu_beats_done
mu_print_two:
        move.l  %d5,-(%sp)
        move.l  %d4,-(%sp)
        move.l  %a1,-(%sp)
        move.l  %a2,-(%sp)
        jsr     0x40013a08
        lea     16(%sp),%sp
        bra.s   mu_beats_done
mu_note_found:
        addq.l  #4,%a1
mu_note_copy:
        move.b  (%a1)+,(%a2)+
        bne.s   mu_note_copy
        bra.s   mu_beats_done
mu_beats_unknown:
        move.b  #63,(%a2)
        clr.b   1(%a2)
mu_beats_done:
        movem.l (%sp),%d2-%d7/%a2
        lea     28(%sp),%sp
        rts
mu_fmt_milli:   .asciz "%ums"
mu_fmt_centi:   .asciz "%u.%02us"
mu_fmt_deci:    .asciz "%u.%us"
mu_fmt_integer: .asciz "%us"
        .balign 2
        .equ MU_NOTE_COUNT,22
mu_note_table:
        .word 4,1
        .asciz "1/1"
        .space 2
        .word 6,1
        .asciz "1/1."
        .space 1
        .word 8,3
        .asciz "1/1T"
        .space 1
        .word 2,1
        .asciz "1/2"
        .space 2
        .word 3,1
        .asciz "1/2."
        .space 1
        .word 4,3
        .asciz "1/2T"
        .space 1
        .word 1,1
        .asciz "1/4"
        .space 2
        .word 3,2
        .asciz "1/4."
        .space 1
        .word 2,3
        .asciz "1/4T"
        .space 1
        .word 1,2
        .asciz "1/8"
        .space 2
        .word 3,4
        .asciz "1/8."
        .space 1
        .word 1,3
        .asciz "1/8T"
        .space 1
        .word 1,4
        .asciz "1/16"
        .space 1
        .word 3,8
        .asciz "1/16."
        .word 1,6
        .asciz "1/16T"
        .word 1,8
        .asciz "1/32"
        .space 1
        .word 3,16
        .asciz "1/32."
        .word 1,12
        .asciz "1/32T"
        .word 1,16
        .asciz "1/64"
        .space 1
        .word 3,32
        .asciz "1/64."
        .word 1,24
        .asciz "1/64T"
        .word 1,32
        .asciz "1/128"

        .balign 2
| Native dial with its held-lock highlight widened to the full 19-pixel
| label area. Only MUSICAL UNITS slots opt in through widget array B.
| Same seven cdecl arguments as 0x400479b4. No parameter/state writes.
        .global mu_widget,mu_bar_widget
mu_bar_widget:
        lea     0x400467a4,%a1
        bra.s   mu_widget_common
mu_widget:
        lea     0x400479b4,%a1
mu_widget_common:
        lea     -20(%sp),%sp
        movem.l %d2-%d3/%a2-%a4,(%sp)
        lea     24(%sp),%a2
        move.l  24(%a2),-(%sp)
        move.l  20(%a2),-(%sp)
        move.l  16(%a2),-(%sp)
        move.l  12(%a2),-(%sp)
        move.l  8(%a2),-(%sp)
        move.l  4(%a2),-(%sp)
        move.l  (%a2),-(%sp)
        jsr     (%a1)
        lea     28(%sp),%sp
        move.l  16(%a2),%d0
        btst    #0,%d0
        beq.s   mu_widget_done
        tst.l   12(%a2)
        bmi.s   mu_widget_done
        move.l  (%a2),%d2
        move.l  4(%a2),%d3
        move.l  %d3,%a4
        addq.l  #1,%d3
        btst    #1,%d0
        beq.s   mu_widget_tall
        addq.l  #7,%a4
        bra.s   mu_widget_edges
mu_widget_tall:
        adda.l  #18,%a4
mu_widget_edges:
        move.l  24(%a2),%a3
        bsr.s   mu_widget_edge
        add.l   #18,%d2
        bsr.s   mu_widget_edge
mu_widget_done:
        movem.l (%sp),%d2-%d3/%a2-%a4
        lea     20(%sp),%sp
        rts
mu_widget_edge:
        moveq   #-1,%d0
        move.l  %d0,-(%sp)
        move.l  %a4,-(%sp)
        move.l  %d2,-(%sp)
        move.l  %d3,-(%sp)
        move.l  %d2,-(%sp)
        move.l  %a3,-(%sp)
        jsr     0x40012254
        lea     24(%sp),%sp
        rts
