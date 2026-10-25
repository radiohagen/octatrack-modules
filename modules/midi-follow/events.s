/* EVENTS notifications. The dispatcher preserves native registers and flags.
 * These callbacks only update Follow history; they never emit MIDI. */
    .text
    .global bf_seq_start,bf_seq_resume,bf_seq_note_accepted

/* d0 = native PLAYING value, after the stock transport write. */
bf_seq_start:
bf_seq_resume:
    jmp bf_register_reset

/* d0 = track, d1 = pool kind, d2 = velocity, d3 = accepted MIDI note.
 * Live keyboard arp output must not advance sequenced GRAV history. */
bf_seq_note_accepted:
    tst.l %d2
    beq.s .done
    cmpi.l #1,%d1
    beq.s .done
    jmp bf_register_sent
.done:
    rts
