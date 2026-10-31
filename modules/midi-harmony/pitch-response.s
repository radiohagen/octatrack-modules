/* Harmony's optional MIDI pitch policy. The build selects this unit only
 * alongside Follow; integration/pitch_response.py documents the generic ABI.
 * Requests never send MIDI, rewrite ownership, or advance arp/history.
 * Preparation retains the existing captured-event synchronization. */
    .text
    .global mh_pitch_capture,mh_pitch_prepare,mh_pitch_owned
    .global mh_pitch_quant,mh_pitch_target,mh_pitch_shift

/* An arp-only tick must retain a generated or keyboard-published root.
 * The live-pool rule also applies with HARM OFF / KEY OFF. */
mh_pitch_capture:
    lea -12(%sp),%sp
    movem.l %d1-%d2/%a0,(%sp)
    move.l %d0,%d2
    jsr mh_active
    andi.l #3,%d0
    bne.s .pitch_capture_owned
    move.l %d2,%d0
    lsl.l #2,%d0
    add.l %d2,%d0
    add.l %d0,%d0
    lea 0x46c77b1e,%a0
    move.b (%a0,%d0.l),%d1
    moveq #0,%d0
    cmpi.b #1,%d1
    bne.s .pitch_capture_done
.pitch_capture_owned:
    moveq #1,%d0
.pitch_capture_done:
    movem.l (%sp),%d1-%d2/%a0
    lea 12(%sp),%sp
    rts

/* Resolve the logical degree before native transpose. Harmony owns scale
 * correction for generated roots, so stock rotation becomes zero. */
mh_pitch_prepare:
    move.l %d1,-(%sp)
    move.l %d7,%d1
    jsr mh_prepare
    move.l (%sp)+,%d1
    cmpi.l #127,%d0
    bhi.s .pitch_prepare_done
    move.l %d0,-(%sp)
    move.l %d7,%d0
    jsr mh_active
    andi.l #3,%d0
    beq.s .pitch_prepare_native
    clr.l %d1
.pitch_prepare_native:
    move.l (%sp)+,%d0
.pitch_prepare_done:
    rts

/* Normalize the setting to a boolean; callers never know Harmony modes. */
mh_pitch_owned:
    jsr mh_active
    andi.l #3,%d0
    beq.s .pitch_owned_done
    moveq #1,%d0
.pitch_owned_done:
    rts

mh_pitch_quant:
    jmp mh_quant

/* Match Harmony's ordinary generator: arranger transpose precedes the
 * final root snap. HARM OFF leaves the already-transposed root unchanged. */
mh_pitch_target:
    lea -12(%sp),%sp
    movem.l %d1-%d2/%a0,(%sp)
    move.l %d1,%d2
    move.l %d0,-(%sp)
    move.l %d2,%d0
    jsr mh_active
    tst.l %d0
    beq.s .pitch_target_native
    move.l (%sp)+,%d0
    lea 0x46c7a124,%a0
    moveq #0,%d1
    move.b (%a0,%d2.l),%d1
    add.l %d1,%d0
    bra.s .pitch_target_quant
.pitch_target_native:
    move.l (%sp)+,%d0
.pitch_target_quant:
    move.l %d2,%d1
    jsr mh_quant
    movem.l (%sp),%d1-%d2/%a0
    lea 12(%sp),%sp
    rts

/* The caller established ownership for this receiver response operation.
 * Both cached arp scratch and held LIVE voices use the same pure transform;
 * invalid pitches return -1. No repeated Part lookup is needed here. */
mh_pitch_shift:
    jmp mh_follow_shift
