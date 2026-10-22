        .text
        | Scale the increment, not the waveform's phase: all native trigger,
        | wrap, HOLD and ONE/HALF handling therefore sees the full pattern.
        .macro eul_audio_clock name, continuation
        .globl \name
\name:
        cmpi.l #19,%d7
        bne.s 1f
        lea -24(%sp),%sp
        movem.l %d1/%a0-%a1,12(%sp)
        move.l %d0,(%sp)
        move.l 28(%sp),4(%sp)
        clr.l 8(%sp)
        jsr eul_scale_increment
        movem.l 12(%sp),%d1/%a0-%a1
        lea 24(%sp),%sp
1:      move.l %d6,24(%a3)
        move.l %d0,(%sp)
        jmp \continuation
        .endm
        eul_audio_clock eul_clock_audio,0x40003c50
        eul_audio_clock eul_clock_inline,0x4000cfea
        .globl eul_clock_midi
eul_clock_midi:
        move.l %d3,%d0
        andi.l #31,%d0
        cmpi.l #19,%d0
        bne.s 2f
        lea -24(%sp),%sp
        movem.l %d1/%a0-%a1,12(%sp)
        move.l 92(%sp),(%sp)
        move.l %d5,%d1
        add.l %d7,%d1
        move.l %d1,4(%sp)
        moveq #1,%d1
        move.l %d1,8(%sp)
        jsr eul_scale_increment
        movem.l 12(%sp),%d1/%a0-%a1
        lea 24(%sp),%sp
        move.l %d0,68(%sp)
        bra.s 3f
2:      move.l 68(%sp),%d0
3:      add.l (%a2),%d0
        jmp 0x40003ef2
        .balign 4
        .globl eul_audio, eul_midi, eul_stock_draw, eul_close
eul_audio:
        moveq #0,%d1
        bra.s eul_dispatch
eul_midi:
        moveq #1,%d1
eul_dispatch:
        | Handler ABI: a0 native state, d0 reset, stack+8 lane index.
        | Native waveform handlers may clobber d0/d1/a0/a1, nothing else.
        move.l %d0,-(%sp)
        move.l %d1,-(%sp)
        move.l 16(%sp),-(%sp)
        move.l %a0,-(%sp)
        jsr eul_wave
        lea 16(%sp),%sp
        rts
eul_stock_draw:
        lea -124(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        jmp 0x400572f0
eul_close:
        clr.l eul_editing
        tst.l 0x400bc038
        jmp 0x40055de6
        | Enter the original SETUP MULT writer after delta/clamp handling.
        | Its Part/SRAM/live writes, dirty flags, refresh and draw are native.
        | Match its 44-byte save frame exactly; no global encoder state edits.
        .globl eul_rate_mult
eul_rate_mult:
        lea -44(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        move.l 48(%sp),%d3
        move.l 52(%sp),%a4
        move.l 56(%sp),%a6
        move.l 60(%sp),%a5
        move.l 64(%sp),%a2
        moveq #2,%d4
        jmp 0x4003932c
        .balign 2
        .globl eul_label
eul_label: .asciz "EUCL"

        | Native WAVE pictogram: own 17x9 stepped pulse train. The native
        | slot 19 icon was NULL; it must not reach the bitmap renderer.
        .balign 4
        .globl eul_icon
eul_icon:
        .long 17,9,1,eul_icon_bits,eul_icon_mask
eul_icon_bits:
        .long 0x01000000,0x01000000,0x7f000000,0x40000000
        .long 0x40000000,0x40000000,0x7f000000,0x01000000
        .long 0x7f000000,0x40000000,0x40000000,0x40000000
        .long 0x7f000000,0x01000000,0x7f000000,0x40000000
        .long 0x40000000
eul_icon_mask:
        .rept 17
        .long 0xff800000
        .endr

        .balign 2
        .globl eul_st_loadall_pre,eul_st_loadmask_pre,eul_st_newproj
        .globl eul_st_bankw_pre,eul_st_bankcopy,eul_st_partsaved,eul_st_partclear
        .globl eul_st_answer,eul_io_refuse
eul_st_loadall_pre:
        jmp eul_load_all
eul_st_newproj:
        jmp eul_new_project
        .globl eul_st_loadall_post,eul_st_loadmask_post,eul_st_tocs1,eul_st_fromcs1
eul_st_loadall_post:
eul_st_loadmask_post:
        jmp eul_load_post
eul_st_tocs1:
        move.l %d0,-(%sp)
        jsr eul_nv_checkpoint
        addq.l #4,%sp
        rts
eul_st_fromcs1:
        move.l %d0,-(%sp)
        jsr eul_nv_boot
        addq.l #4,%sp
        rts
eul_st_loadmask_pre:
        move.l %d1,-(%sp)
        jsr eul_load_mask
        addq.l #4,%sp
        rts
eul_st_bankw_pre:
        move.l %d1,-(%sp)
        jsr eul_write_mask
        addq.l #4,%sp
        rts
eul_st_bankcopy:
        move.l %d1,-(%sp)
        move.l %d0,-(%sp)
        jsr eul_bank_copy
        addq.l #8,%sp
        rts
eul_st_partsaved:
        move.l %d0,-(%sp)
        jsr eul_part_save
        addq.l #4,%sp
        rts
eul_st_partclear:
        move.l %d0,-(%sp)
        jsr eul_part_clear
        addq.l #4,%sp
        rts
eul_st_answer:
        move.l %d1,-(%sp)
        move.l %d0,-(%sp)
        jsr eul_answer
        addq.l #8,%sp
        rts
eul_io_refuse:
        move.l 4(%sp),%d1
        moveq #3,%d0
        jmp store_refuse

        .globl eul_capture_clip,eul_capture_undo
eul_capture_clip:
        clr.l -(%sp)
        move.l 8(%sp),-(%sp)   | original memcpy's source, still on the stack
        jsr eul_capture_part
        addq.l #8,%sp
        moveq #17,%d0          | replay the displaced clipboard-kind store
        move.l %d0,0x460d0ffa
        jmp 0x40029360
eul_capture_undo:
        pea 1
        move.l 8(%sp),-(%sp)
        jsr eul_capture_part
        addq.l #8,%sp
        moveq #17,%d0
        move.l %d0,0x460c80f0
        jmp 0x40029324
