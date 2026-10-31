/* C ABI adapters to the shared explicit-context native Part interface. */
    .include "remix.inc"
    .text
    .global hd_follow_c,hd_scale_read_c
hd_follow_c:
    moveq #HD_FOLLOW,%d0
    rts
/* C ABI: local track, explicit provider context -> unchanged legacy identity.
 * The provider selection already rejects unsupported Harmony catalogues. */
hd_scale_read_c:
    move.l 4(%sp),%d0
    move.l 8(%sp),%d1
    scale_read
    tst.l %d0
    bmi.s .scale_read_off
    scale_legacy
    rts
.scale_read_off:
    moveq #-1,%d0 /* Same unavailable native KEY convention as before. */
    rts
    .global hd_scenes_c
hd_scenes_c:
    moveq #HD_SCENES,%d0
    rts
    .global hd_ui_context_c,hd_play_context_c,hd_part_read_c,hd_part_write_c,hd_part_key_c
hd_ui_context_c:
    jmp store_part_ui_context
hd_play_context_c:
    move.l 4(%sp),%d0
    jmp store_part_midi_context
hd_part_key_c:
    move.l 4(%sp),%d0
    move.l 8(%sp),%d1
    jmp store_part_midi_key
hd_part_read_c:
    move.l %d2,-(%sp)
    move.l 8(%sp),%d0
    move.l 12(%sp),%d1
    move.l 16(%sp),%d2
    jsr store_part_midi_read
    move.l (%sp)+,%d2
    rts
hd_part_write_c:
    lea -8(%sp),%sp
    movem.l %d2-%d3,(%sp)
    move.l 12(%sp),%d0
    move.l 16(%sp),%d1
    move.l 20(%sp),%d2
    move.l 24(%sp),%d3
    jsr store_part_midi_write
    movem.l (%sp),%d2-%d3
    addq.l #8,%sp
    rts

/* Shared native replacement boundary: d0 outgoing Part address, all kept. */
    .global hd_part_before
hd_part_before:
    lea -16(%sp),%sp
    movem.l %d0-%d1/%a0-%a1,(%sp)
    move.l %d0,-(%sp)
    jsr hd_part_before_c
    addq.l #4,%sp
    movem.l (%sp),%d0-%d1/%a0-%a1
    lea 16(%sp),%sp
    rts

/* d0 = native bank pointer, all registers preserved. */
    .global hd_scenes_before
hd_scenes_before:
    lea -16(%sp),%sp
    movem.l %d0-%d1/%a0-%a1,(%sp)
    move.l %d0,-(%sp)
    jsr hd_scenes_before_c
    addq.l #4,%sp
    movem.l (%sp),%d0-%d1/%a0-%a1
    lea 16(%sp),%sp
    rts
