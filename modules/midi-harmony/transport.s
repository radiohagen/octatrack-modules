/* EVENTS clients. Musical policy belongs to Harmony. */
    .text
    .global mh_seq_start,mh_seq_resume,mh_seq_note_accepted
mh_seq_start:
mh_seq_resume:
    jmp ha_transport_c
mh_seq_note_accepted:
    tst.l %d2
    beq.s mh_seq_done
    cmpi.l #1,%d1
    beq.s mh_seq_done
    move.l %d0,%d7
    jmp ha_note_sent
mh_seq_done:
    rts
