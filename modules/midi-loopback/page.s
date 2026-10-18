/* CHAN press retains the native staged channel commit, then opens routing.
 * A edits DEST. Transport/chromatic input passes through the native modal.
 * Other encoders/pushes cannot accidentally edit staged NOTE SETUP fields.
 */
    .include "remix.inc"
    .text
    .global lb_channel_press,lb_channel_format,lb_page_open,lb_page_close
    .global lb_page_noop,lb_page_encoder,lb_page_draw,lb_page_win,lb_page_track
    .global lb_dest_format
lb_channel_press:
    move.l 8(%sp),-(%sp)
    move.l 8(%sp),-(%sp)
    jsr 0x4004ae08
    addq.l #8,%sp
    jsr lb_part_sync
    jsr lb_sync
    bra.w lb_page_open
lb_page_open:
    tst.l lb_page_win
    bne.w lb_page_close
    moveq #0,%d0
    move.b 0x100b14cc,%d0
    cmpi.l #7,%d0
    bhi.s lb_page_noop
    move.l %d0,lb_page_track
    pea lb_page_close
    pea 5 /* stock modal class, shared with TEMPO/Tuner */
    clr.l -(%sp)
    clr.l -(%sp)
    pea 60
    pea 120
    jsr 0x4005829c
    lea 24(%sp),%sp
    move.l %d0,lb_page_win
    beq.s lb_page_noop
    move.l %d0,-(%sp)
    jsr 0x40056f4c
    addq.l #4,%sp
    pea lb_page_layer
    jsr 0x40031494
    addq.l #4,%sp
    bra.w lb_page_draw
lb_page_noop:
    rts
lb_page_close:
    tst.l lb_page_win
    beq.s lb_page_noop
    pea lb_page_win
    jsr 0x40055db4
    addq.l #4,%sp
    pea lb_page_layer
    jsr 0x4003146c
    addq.l #4,%sp
    jmp 0x40036548 /* redraw NOTE SETUP from current module values */

lb_page_encoder:
    .ifdef HAVE_TRANSLATION
    move.l 4(%sp),%d0
    beq.s .route_encoder
    cmpi.l #4,%d0
    bhi.w lb_page_noop
    jmp lt_page_encoder
.route_encoder:
    .endif
    tst.l 4(%sp)
    bne.s lb_page_noop
    move.l %d2,-(%sp)
    move.l 12(%sp),%d1
    cmpi.l #4,%d1
    ble.s .delta_low
    moveq #4,%d1
.delta_low:
    cmpi.l #-4,%d1
    bge.s .delta_apply
    moveq #-4,%d1
.delta_apply:
    pea 1024
    move.l %d1,-(%sp)
    clr.l -(%sp)
    jsr 0x40032510
    lea 12(%sp),%sp
    move.l %d0,%d2
    move.l lb_page_track,%d0
    jsr lb_dest_get
    add.l %d2,%d0
    bpl.s .delta_max
    moveq #0,%d0
.delta_max:
    cmpi.l #2,%d0
    ble.s .delta_store
    moveq #2,%d0
.delta_store:
    move.l %d0,%d1
    move.l lb_page_track,%d0
    jsr lb_dest_set
    move.l (%sp)+,%d2
    bra.w lb_page_draw
lb_page_draw:
    lea -44(%sp),%sp
    movem.l %d2-%d3/%a2/%a5,(%sp)
    lea 16(%sp),%a2 /* 28-byte text scratch */
    move.l lb_page_win,%d0
    beq.w .page_draw_done
    move.l %d0,%a5
    lea 36(%a5),%a5
    move.l %a5,-(%sp)
    jsr 0x40035624
    addq.l #4,%sp
    /* Native PLAYBACK selectors: exact count, with our value formatters.
     * ABI: widget(x,y,slot,value,flags,formatter,surface).
     * Full layout, no lock highlight; the modal owns its own surface.
     */
    move.l lb_page_track,%d0
    jsr lb_dest_get
    move.l %d0,%d1
    moveq #10,%d0
    lea lb_dest_format,%a0
    lea 0x40046d9c,%a1
    bsr.w .page_selector
    .ifdef HAVE_TRANSLATION
    moveq #0,%d3
.translation_cell:
    move.l %d3,-(%sp)
    move.l lb_page_track,-(%sp)
    jsr lt_ui_get
    addq.l #8,%sp
    move.l %d0,%d1
    lea .translation_cells,%a0
    move.l %d3,%d0
    lsl.l #4,%d0
    adda.l %d0,%a0
    move.l (%a0),%d0
    move.l 8(%a0),%a0
    lea 0x400467a4,%a1 /* stock NOTE-style text for references and range */
    tst.l %d3
    bne.s .translation_widget
    lea 0x40046c28,%a1 /* native four-position selector, including BOTH */
.translation_widget:
    cmpi.l #2,%d3
    bcc.s .translation_bottom
    bsr.w .page_selector
    bra.s .translation_label
.translation_bottom:
    cmpi.l #3,%d3
    bne.s .translation_rotary
    lsl.l #1,%d1 /* radius 0..63 uses the native dial's full travel */
.translation_rotary:
    lea 0x400479b4,%a1 /* complete stock rotary control, value below */
    bsr.w .page_selector_bottom
.translation_label:
    lea .translation_cells,%a0
    move.l %d3,%d0
    lsl.l #4,%d0
    adda.l %d0,%a0
    move.l (%a0),%d0
    addi.l #9,%d0
    add.l 4(%a0),%d0 /* fixed-label optical inset, measured on composed pixels */
    move.l 12(%a0),%a0
    moveq #52,%d1
    cmpi.l #2,%d3
    bcs.s .translation_text
    moveq #23,%d1
.translation_text:
    bsr.w .page_center_text
    addq.l #1,%d3
    cmpi.l #4,%d3
    bne.w .translation_cell
    .endif
    bsr.w .page_grid
    .ifndef HAVE_TRANSLATION
    move.l lb_page_track,%d0
    addq.l #1,%d0
    move.l %d0,-(%sp)
    pea .page_title
    move.l %a2,-(%sp)
    jsr 0x40013a08
    lea 12(%sp),%sp
    moveq #4,%d0
    moveq #4,%d1
    move.l %a2,%a0
    bsr.w .page_text
    .endif
    moveq #12,%d0
    moveq #52,%d1
    lea .page_dest_label,%a0
    bsr.w .page_text
    .ifndef HAVE_TRANSLATION
    moveq #85,%d0
    moveq #4,%d1
    lea .page_back,%a0
    bsr.w .page_text
    .endif
    moveq #1,%d0
    move.l %d0,0x46c7c72c
.page_draw_done:
    movem.l (%sp),%d2-%d3/%a2/%a5
    lea 44(%sp),%sp
    rts
.page_grid: /* Stock line/box primitive; translation uses two full-height rows. */
    lea -8(%sp),%sp
    movem.l %d2/%a2,(%sp)
    .ifdef HAVE_TRANSLATION
    moveq #3,%d2
    .else
    moveq #4,%d2
    .endif
    lea .page_grid_lines,%a2
.page_grid_line:
    pea 1
    move.l 12(%a2),-(%sp)
    move.l 8(%a2),-(%sp)
    move.l 4(%a2),-(%sp)
    move.l (%a2),-(%sp)
    move.l %a5,-(%sp)
    jsr 0x40012254
    lea 24(%sp),%sp
    lea 16(%a2),%a2
    subq.l #1,%d2
    bne.s .page_grid_line
    movem.l (%sp),%d2/%a2
    lea 8(%sp),%sp
    rts
.page_selector_bottom:
    .ifdef HAVE_TRANSLATION
    moveq #4,%d2
    .else
    moveq #13,%d2
    .endif
    bra.s .page_selector_y
.page_selector: /* d0=x,d1=value,a0=formatter,a1=stock widget,a5=surface */
    moveq #36,%d2
.page_selector_y:
    move.l %a5,-(%sp)
    move.l %a0,-(%sp)
    .ifdef HAVE_TRANSLATION
    cmpa.l #0x400479b4,%a1
    bne.s .page_plain_flags
    pea 8 /* native fixed rotary layout, no lock highlight */
    bra.s .page_widget_args
.page_plain_flags:
    .endif
    clr.l -(%sp) /* flags: full widget, no highlight */
.page_widget_args:
    move.l %d1,-(%sp)
    clr.l -(%sp) /* slot is unused by these stock widgets */
    move.l %d2,-(%sp)
    move.l %d0,-(%sp)
    jsr (%a1)
    lea 28(%sp),%sp
    rts
    .ifdef HAVE_TRANSLATION
.page_center_text: /* centered labels use the same native width as values */
    move.l %d0,-(%sp)
    move.l %d1,-(%sp)
    move.l %a0,-(%sp)
    move.l %a0,-(%sp)
    pea -1
    pea 0x400ba876
    jsr 0x40012f30
    lea 12(%sp),%sp
    move.l (%sp)+,%a0
    move.l (%sp)+,%d1
    move.l (%sp)+,%d2
    lsr.l #1,%d0
    sub.l %d0,%d2
    move.l %d2,%d0
    .endif
.page_text: /* d0=x,d1=y,a0=string,a5=surface; native C ABI */
    move.l %a0,-(%sp)
    pea -1
    move.l %d1,-(%sp)
    move.l %d0,-(%sp)
    move.l %a5,-(%sp)
    pea 0x400ba876
    jsr 0x40012bd8
    lea 24(%sp),%sp
    rts
lb_dest_format:
    move.l 4(%sp),%a0
    move.l 8(%sp),%d0
    lea .ext,%a1
    cmpi.l #1,%d0
    bne.s .format_both
    lea .int,%a1
    bra.s .format_copy
.format_both:
    cmpi.l #2,%d0
    bne.s .format_copy
    lea .both,%a1
.format_copy:
    move.b (%a1)+,(%a0)+
    bne.s .format_copy
    rts
/* Same CHAN formatter ABI. Stock formats OFF/1..16; append I or B only.
 * Five characters maximum (OFF plus marker), within the native value cell. */
lb_channel_format:
    move.l %a2,-(%sp)
    move.l 8(%sp),%a2
    move.l 12(%sp),-(%sp)
    move.l %a2,-(%sp)
    jsr 0x4003c770
    addq.l #8,%sp
    moveq #0,%d0
    move.b 0x100b14cc,%d0
    jsr lb_dest_get
    tst.l %d0
    beq.s .channel_done
.channel_end:
    tst.b (%a2)+
    bne.s .channel_end
    moveq #73,%d1
    cmpi.l #1,%d0
    beq.s .channel_marker
    moveq #66,%d1
.channel_marker:
    move.b %d1,-1(%a2)
    clr.b (%a2)
.channel_done:
    move.l (%sp)+,%a2
    rts
.page_dest_label: .asciz "DEST"
    .ifdef HAVE_TRANSLATION
.label_apply: .asciz "RE-MAP"
.label_source: .asciz "SRC REF"
.label_target: .asciz "TGT REF"
.label_range: .asciz "RANGE"
    .balign 4
.translation_cells:
    .long 49,0,lt_apply_format,.label_apply
    .long 88,0,lt_note_format,.label_source
    .long 10,1,lt_number_format,.label_target
    .long 49,0,lt_range_format,.label_range
    .endif
.page_title: .asciz "ROUTING M%d"
.page_back: .asciz "NO:BACK"
.ext: .asciz "EXT"
.int: .asciz "INT"
.both: .asciz "BOTH"
    .balign 4
.page_grid_lines:
    .ifdef HAVE_TRANSLATION
    .long 38,1,38,58
    .long 77,1,77,58
    .long 1,29,117,29
    .else
    .long 38,12,38,58
    .long 77,12,77,58
    .long 1,35,117,35
    .long 1,12,117,12
    .endif
lb_page_layer:
    .long 0,lb_page_keys,lb_page_encs,0,0,-1,-1
lb_page_keys:
    /* Track keys inherit stock dispatch: close the modal and select in one press. */
    /* The opening A key's release is consumed; only a new press closes. */
    .irp key,0x31,0x32,0x38,0x22,0x23,0x24,0x25,0x26,0x35
    .byte \key,0
    .long lb_page_close,0x4004ae08,0,0,0
    .word 0,0
    .endr
    /* Held knob pushes must not commit stock NOTE SETUP values. */
    .irp key,0x39,0x3a,0x3b,0x3c,0x3d
    .byte \key,0
    .long 0,0,0,0,0
    .word 0,0
    .endr
    .byte 0xff,0
    .long 0,0,0,0,0
    .word 0,0
lb_page_encs:
    .irp knob,0,1,2,3,4,5,6
    .byte \knob,0
    .long lb_page_encoder,0,0,0,0
    .endr
    .byte 0xff,0
    .long 0,0,0,0,0
    .balign 4
lb_page_win: .long 0
lb_page_track: .long 0
