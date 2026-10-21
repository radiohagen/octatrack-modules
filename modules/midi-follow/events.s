/* SEQUENCER EVENTS clients. Follow owns register history policy. */
    .text
    .global bf_seq_start,bf_seq_resume,bf_seq_midi_sent
bf_seq_start:
bf_seq_resume:
    jmp bf_register_reset
bf_seq_midi_sent:
    tst.l %d2
    beq.s bf_seq_done
    cmpi.l #1,%d1
    beq.s bf_seq_done
    jmp bf_register_sent
bf_seq_done:
    rts
