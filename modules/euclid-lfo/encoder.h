#ifndef EUCLID_LFO_ENCODER_H
#define EUCLID_LFO_ENCODER_H
/* Editor-only resistance. Never alter the native encoder accumulators or
 * saved parameter resolution. Pattern/rate choices: four panel counts;
 * OUT/DIR: eight; swing: two; 0..127 amounts: one. No push/velocity gain. */
static unsigned eul_encoder_counts(unsigned field) {
    if(field==3 || field==10) return 8;
    if(field==9) return 2;
    if(field==4 || field==5 || field==8) return 1;
    return 4;
}
static int eul_encoder_turn(unsigned field,int raw,unsigned value,
                            unsigned low,unsigned high,int *residue) {
    if(!raw) return 0;
    if((raw<0 && value<=low) || (raw>0 && value>=high) || low==high) {
        *residue=0; return 0;
    }
    if(raw>127) raw=127;
    if(raw< -127) raw=-127;
    /* Reversing must not first pay back unfinished motion in the old
     * direction. Same-direction UART coalescing retains every count. */
    if((raw<0 && *residue>0) || (raw>0 && *residue<0)) *residue=0;
    int sum=raw+*residue,counts=(int)eul_encoder_counts(field);
    int delta=sum/counts;
    *residue=sum-delta*counts;
    if(delta && ((int)value+delta<=(int)low || (int)value+delta>=(int)high)) *residue=0;
    return delta;
}
#endif
