/* Register/C ABI boundaries. Never mutate a producer's packet. */
    .text
    .global lt_play_context,lt_ui_context,lt_lock,lt_unlock,lt_emit
lt_play_context:
    move.l 4(%sp),%d0
    jmp lb_play_context
lt_ui_context:
    jmp mp_ui_context
lt_lock:
    moveq #0,%d0
    move.w %sr,%d0
    move.w #0x2700,%sr
    rts

    .global lt_path,lt_fopen,lt_fread,lt_fwrite,lt_fclose,lt_fsize
    .global lt_exists,lt_fcopy,lt_crc,lt_refuse
lt_path:
    move.l 4(%sp),%d0
    addq.l #1,%d0
    move.l 8(%sp),%a1
    lea .lt_file,%a0
    jmp store_path
lt_fopen:
    move.l %a2,-(%sp)
    move.l 8(%sp),%a0
    move.l 12(%sp),%a1
    move.l 16(%sp),%a2
    jsr store_fopen
    move.l (%sp)+,%a2
    rts
    .macro LT_IO name,target
\name:
    move.l %a2,-(%sp)
    move.l 8(%sp),%a2
    move.l 12(%sp),%a0
    move.l 16(%sp),%d0
    jsr \target
    move.l (%sp)+,%a2
    rts
    .endm
    LT_IO lt_fread,store_fread
    LT_IO lt_fwrite,store_fwrite
lt_fclose:
    move.l %a2,-(%sp)
    move.l 8(%sp),%a2
    jsr store_fclose
    move.l (%sp)+,%a2
    rts
lt_fsize:
    jmp 0x400148d4
lt_exists:
    move.l 0x46c823fa,%a0
    jmp (%a0)
lt_fcopy:
    jmp 0x40016388
lt_crc:
    move.l 4(%sp),%a0
    move.l 8(%sp),%d0
    moveq #0,%d1
    jmp store_crc32
lt_refuse:
    move.l 4(%sp),%d1
    moveq #3,%d0
    jmp store_refuse

    .global lt_st_loadall_post,lt_st_loadmask_post,lt_st_newproj,lt_st_newproj_post
    .global lt_st_bankw_guard,lt_st_bankcopy_guard,lt_st_bankcopy_done,lt_st_answer
    .global lt_st_fromcs1
lt_st_fromcs1:
    /* CS1 restoration precedes the filesystem. Defer that skipped bank to
     * the next normal disk-load completion; never do file I/O here. */
    cmpi.l #15,%d0
    bhi.s .lt_resume_done
    moveq #1,%d1
    lsl.l %d0,%d1
    or.l %d1,lt_resume_mask
.lt_resume_done:
    rts
lt_st_loadall_post:
    clr.l lt_resume_mask
    move.l #65535,-(%sp)
    jsr lt_load_banks
    addq.l #4,%sp
    rts
lt_st_loadmask_post:
    or.l lt_resume_mask,%d1
    clr.l lt_resume_mask
    move.l %d1,-(%sp)
    jsr lt_load_banks
    addq.l #4,%sp
    rts
lt_st_newproj:
lt_st_newproj_post:
    clr.l lt_resume_mask
    jmp lt_new_project
lt_st_bankw_guard:
    move.l %d1,-(%sp)
    jsr lt_save_banks
    addq.l #4,%sp
    rts
lt_st_bankcopy_guard:
    move.l %d1,-(%sp)
    jsr lt_copy_guard
    addq.l #4,%sp
    rts
lt_st_bankcopy_done:
    move.l %d1,-(%sp)
    move.l %d0,-(%sp)
    jsr lt_copy_done
    addq.l #8,%sp
    rts
lt_st_answer:
    move.l %d1,-(%sp)
    move.l %d0,-(%sp)
    jsr lt_answer
    addq.l #8,%sp
    rts
.lt_file: .asciz "%s/lbnt%02d.work"
    .balign 4
    .global lt_mark_dirty
lt_mark_dirty:
    move.l %d2,-(%sp)
    move.l 8(%sp),%d0
    move.l %d0,%d1
    andi.l #3,%d1
    lsr.l #2,%d0
    move.l #0x9b340,%d2
    mulu.l %d2,%d0
    addi.l #0x400e21e0,%d0
    move.l %d0,%a0
    move.l %a0,%a1
    adda.l #0x95048,%a1
    bset %d1,(%a1)
    moveq #1,%d0
    move.l %a0,%a1
    adda.l #0x9b332,%a1
    move.l %d0,(%a1)
    cmpa.l 0x46c82456,%a0
    bne.s .lt_dirty_done
    bset %d1,0x100b145e
    move.l %d0,0x100f8598
.lt_dirty_done:
    move.l (%sp)+,%d2
    rts

    .global lt_page_encoder
lt_page_encoder:
    lea -8(%sp),%sp
    movem.l %d2-%d3,(%sp)
    move.l 12(%sp),%d3
    subq.l #1,%d3
    beq.s .lt_encoder_enabled
    clr.l -(%sp)
    move.l lb_page_track,-(%sp)
    jsr lt_ui_get
    addq.l #8,%sp
    tst.l %d0
    ble.w .lt_encoder_done
.lt_encoder_enabled:
    move.l 16(%sp),%d1
    cmpi.l #4,%d1
    ble.s .lt_delta_low
    moveq #4,%d1
.lt_delta_low:
    cmpi.l #-4,%d1
    bge.s .lt_delta
    moveq #-4,%d1
.lt_delta:
    pea 1024
    move.l %d1,-(%sp)
    clr.l -(%sp)
    jsr 0x40032510
    lea 12(%sp),%sp
    move.l %d0,%d2
    move.l %d3,-(%sp)
    move.l lb_page_track,-(%sp)
    jsr lt_ui_get
    addq.l #8,%sp
    add.l %d2,%d0
    bpl.s .lt_value_max
    moveq #0,%d0
.lt_value_max:
    moveq #127,%d1
    cmpi.l #3,%d3
    bne.s .lt_value_mode_max
    moveq #63,%d1
.lt_value_mode_max:
    tst.l %d3
    bne.s .lt_clamp
    moveq #3,%d1
.lt_clamp:
    cmp.l %d1,%d0
    bls.s .lt_value_store
    move.l %d1,%d0
.lt_value_store:
    move.l %d0,-(%sp)
    move.l %d3,-(%sp)
    move.l lb_page_track,-(%sp)
    jsr lt_ui_set
    lea 12(%sp),%sp
.lt_encoder_done:
    movem.l (%sp),%d2-%d3
    addq.l #8,%sp
    jmp lb_page_draw
lt_unlock:
    move.l 4(%sp),%d0
    move.w %d0,%sr
    rts
    .data
    .balign 4
lt_resume_mask: .long 0
    .text
/* d0=0x100|translated note, a0=original three-byte note packet.
 * Only proven note producers call this, after capture admitted EXT. */
lt_emit:
    subq.l #4,%sp
    move.b (%a0),(%sp)
    move.b %d0,1(%sp)
    move.b 2(%a0),2(%sp)
    clr.b 3(%sp)
    pea (%sp)
    pea 3
    jsr 0x40010bc8
    addq.l #8,%sp
    addq.l #4,%sp
    rts
