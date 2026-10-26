/* SPDX-License-Identifier: MIT
 * Opt-in SS_DIAGNOSTICS=1 only. No USB, allocation, printf or audio writes.
 * DTCN3 is the same 132 MHz free-running timer used by LOAD METER. These
 * durations include interrupt/bus delays; they are not exclusive CPU cycles.
 */
extern uint8_t ss_native_state[], ss_native_voices[], ss_native_clock[];
struct ss_diag_cost { uint32_t calls, last, maximum, sum; };
struct ss_diag_event_record {
    uint32_t sequence, frame, ticks, kind, track, note, selected, stamp;
};
struct ss_diag_snapshot {
    uint32_t sequence, frame, samples, selected, poly, mono_gain, mono_previous;
    uint32_t state[4], gain[4], previous[4], age[4], wet[5];
};
/* Independent producers: MIDI input owns ring 0; audio owns ring 1.
 * A record is published by writing its sequence last. Readers must reread
 * sequence and reject zero/changed records; old records wrap after 64 events.
 */
volatile struct ss_diag_event_record ss_diag_events[2][64] = {{{0}}};
volatile uint32_t ss_diag_sequence[2] = {0};
volatile struct ss_diag_snapshot ss_diag_tracks[8] = {{0}};
/* Stages: 0 selector/config/reset, 1 renderer/mix, 2 native allocator.
 * Sums wrap modulo 2^32; use deltas over short windows, not lifetime means. */
volatile struct ss_diag_cost ss_diag_costs[8][3] = {{{0}}};
static uint32_t ss_diag_alloc_start[8] = {0};
static uint32_t ss_diag_now(void) { return *(volatile uint32_t *)0xfc07c00cu; }
static uint32_t ss_diag_frame(void) { return *(volatile uint32_t *)(ss_native_clock+12); }
static void ss_diag_cost(unsigned track,unsigned stage,uint32_t ticks) {
    volatile struct ss_diag_cost *p=&ss_diag_costs[track][stage];
    p->last=ticks;p->sum+=ticks;++p->calls;
    if(ticks>p->maximum)p->maximum=ticks;
}
void ss_diag_event(unsigned track,unsigned kind,unsigned note) {
    if(track>=8)return;
    uint32_t ticks=ss_diag_now();
    if(kind==5)ss_diag_cost(track,2,ticks-ss_diag_alloc_start[track]);
    unsigned ring=kind<=2?0:1;
    uint32_t sequence=ss_diag_sequence[ring]+1;
    if(!sequence)sequence=1;
    volatile struct ss_diag_event_record *e=&ss_diag_events[ring][sequence&63];
    e->sequence=0;e->frame=ss_diag_frame();e->ticks=ticks;
    e->kind=kind;e->track=track;e->note=note;
    e->selected=ss_active[track];e->stamp=ss_note_stamp[track];
    e->sequence=sequence;ss_diag_sequence[ring]=sequence;
    if(kind==4)ss_diag_alloc_start[track]=ss_diag_now();
}
void ss_begin(uint32_t track,const uint8_t *state) {
    uint32_t start=ss_diag_now();
    ss_begin_impl(track,state);
    uint32_t elapsed=ss_diag_now()-start;
    if(track<8) { ss_diag_cost(track,0,elapsed);ss_diag_event(track,6,0); }
}
int ss_track_fill(uint32_t track,uint8_t *state,const uint16_t *fp,
                  int32_t *out,uint32_t n,uint8_t *pool) {
    uint32_t previous[4]={0},mono_previous=0;
    if(track<8) {
        mono_previous=*(uint16_t *)(state+38);
        for(unsigned v=0;v<4;++v)previous[v]=*(uint16_t *)(pool+64*v+60);
    }
    uint32_t start=ss_diag_now();
    int result=ss_track_fill_impl(track,state,fp,out,n,pool);
    uint32_t elapsed=ss_diag_now()-start;
    if(track<8) {
        ss_diag_cost(track,1,elapsed);
        volatile struct ss_diag_snapshot *s=&ss_diag_tracks[track];
        uint32_t sequence=s->sequence+2;
        s->sequence=sequence|1;
        s->frame=ss_diag_frame();s->samples=n;s->selected=ss_active[track];
        s->poly=state[80];s->mono_gain=*(uint32_t *)(state+24);
        s->mono_previous=mono_previous;
        for(unsigned v=0;v<4;++v) {
            const uint8_t *p=pool+64*v;
            s->state[v]=p[36];s->gain[v]=*(const uint32_t *)(p+24);
            s->previous[v]=previous[v];
            s->age[v]=*(const uint32_t *)(p+48);
        }
        for(unsigned v=0;v<5;++v)s->wet[v]=ss_filters[track][v].wet;
        s->sequence=sequence;
    }
    return result;
}
