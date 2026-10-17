/* Uncalled compatibility tail retained for exact tested runtime bytes.
 * Native boot calls mp_activate directly; no hook may target this stub.
 * Removing it changes the packed runtime/image and needs fresh boot evidence.
 */
    .text
    .global startup_layout_tail
startup_layout_tail:
    move.l %d0,-(%sp)
    moveq #3,%d0
    jsr startup_trace
    move.l (%sp)+,%d0
    jmp mp_activate
