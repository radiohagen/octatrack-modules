/* Compiled twice against independent engine headers. Do not compare EulState
 * bytes: runtime-only caches may change layout without changing behavior. */
#include <engine.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    EulParams params, source;
    uint16_t hits, accents, values[16];
    uint32_t rng, phase, origin, target, level;
    uint8_t ready, last_hit, last_step;
} Observation;

static void observe(const EulState *state, Observation *out) {
    memset(out, 0, sizeof(*out));
    out->params=state->params; out->source=state->source;
    out->hits=state->hits; out->accents=state->accents;
    memcpy(out->values, state->values, sizeof(out->values));
    out->rng=state->rng; out->phase=state->phase;
    out->origin=state->origin; out->target=state->target; out->level=state->level;
    out->ready=state->ready; out->last_hit=state->last_hit;
    out->last_step=state->last_step;
}

#ifdef EUL_REFERENCE
static EulState reference;
void reference_clear(void) { memset(&reference, 0, sizeof(reference)); }
int32_t reference_process(const EulParams *p, uint32_t phase, unsigned reset,
                          unsigned terminal, unsigned identity) {
    return eul_process(&reference,p,phase,reset,terminal,identity);
}
void reference_observe(Observation *out) { observe(&reference,out); }
#else
void reference_clear(void);
int32_t reference_process(const EulParams *,uint32_t,unsigned,unsigned,unsigned);
void reference_observe(Observation *);
void baseline_eul_defaults(EulParams *);
void baseline_eul_normalize(EulParams *);
void baseline_eul_masks(const EulParams *,uint16_t *,uint16_t *);
unsigned baseline_eul_edit(EulParams *,unsigned,int);
int32_t baseline_eul_clock(int32_t,unsigned,int32_t *);
int32_t baseline_eul_audio_clock(int,unsigned,unsigned,unsigned,int32_t *);

static EulState candidate;
static uint32_t random_state=0x27c010e5u;
static unsigned long process_cases, mask_cases, clock_cases, edit_cases;
static const char *section;
static unsigned negative_control;

static uint32_t next_random(void) {
    uint32_t value=random_state;
    value^=value<<13; value^=value>>17; value^=value<<5;
    return random_state=value;
}
static void mismatch(const char *what, int64_t actual, int64_t expected) {
    fprintf(stderr,"%s mismatch: %s (actual=%lld expected=%lld, process=%lu "
            "masks=%lu clocks=%lu edits=%lu)\n",section,what,
            (long long)actual,(long long)expected,process_cases,mask_cases,
            clock_cases,edit_cases);
    exit(1);
}
#define EQUAL(what,actual,expected) do { \
    if ((actual)!=(expected)) mismatch(what,(actual),(expected)); \
} while (0)

static void clear_states(void) {
    memset(&candidate,0,sizeof(candidate));
    reference_clear();
}

static void process(const EulParams *p,uint32_t phase,unsigned reset,
                    unsigned terminal,unsigned identity) {
    ++process_cases;
    int32_t actual=eul_process(&candidate,p,phase,reset,terminal,identity);
    int32_t expected=reference_process(p,phase,reset,terminal,identity);
    if (negative_control && actual) actual^=256;
    if(actual!=expected) {
        fprintf(stderr,"params=%u,%u,%u,%u,%u,%u,%u,%u,%u,%u "
                "phase=%u reset=%u terminal=%u identity=%u\n",
                p->steps,p->pulses,p->rotate,p->mode,p->attack,p->decay,
                p->accents,p->accent_rotate,p->boost,p->swing,
                phase,reset,terminal,identity);
        mismatch("output",actual,expected);
    }
    Observation a,b;
    observe(&candidate,&a); reference_observe(&b);
    if(memcmp(&a.params,&b.params,sizeof(a.params))) mismatch("params",1,0);
    if(memcmp(&a.source,&b.source,sizeof(a.source))) mismatch("source",1,0);
#define STATE(field) EQUAL(#field,a.field,b.field)
    STATE(hits); STATE(accents); STATE(rng); STATE(phase); STATE(origin);
    STATE(target); STATE(level); STATE(ready); STATE(last_hit); STATE(last_step);
#undef STATE
    for(unsigned i=0;i<16;++i) EQUAL("random history",a.values[i],b.values[i]);
}

static void masks(const EulParams *p) {
    uint16_t hits,accents,old_hits,old_accents;
    eul_masks(p,&hits,&accents);
    baseline_eul_masks(p,&old_hits,&old_accents);
    ++mask_cases;
    EQUAL("hits",hits,old_hits); EQUAL("accents",accents,old_accents);
}

static void exhaustive_masks(void) {
    section="exhaustive mask/rotation/accents";
    EulParams p;
    eul_defaults(&p);
    for(unsigned n=1;n<=16;++n) for(unsigned k=0;k<=n;++k)
        for(unsigned r=0;r<n;++r) for(unsigned a=0;a<=k;++a)
            for(unsigned ar=0;ar<(k?k:1);++ar) {
                p.steps=n; p.pulses=k; p.rotate=r;
                p.accents=a; p.accent_rotate=ar;
                masks(&p);
            }
}

/* Smallest integer phase whose quantized position reaches this exact edge. */
static uint32_t phase_at(unsigned position,unsigned steps) {
    return (position*2048u+steps-1u)/steps;
}
static void around(const EulParams *p,unsigned position,unsigned identity) {
    uint32_t at=phase_at(position,p->steps);
    if(at) process(p,at-1,0,0,identity);
    process(p,at,0,0,identity);
    process(p,at+1,0,0,identity);
}

static void timing_edges(void) {
    section="step/swing edges forward and reverse";
    EulParams p;
    eul_defaults(&p);
    for(unsigned n=1;n<=16;++n) for(unsigned k=0;k<=n;++k)
        for(unsigned r=0;r<n;++r) for(unsigned swing=0;swing<=30;++swing) {
            p.steps=n; p.pulses=k; p.rotate=r; p.swing=swing;
            p.mode=(n+k+r+swing)&7; p.attack=(n*17+k*7+swing)&127;
            p.decay=(n*3+r*11+swing)&127; p.accents=k/2;
            p.accent_rotate=k?r%k:0; p.boost=(k*11+swing)&127;
            clear_states();
            for(unsigned i=0;i<n;++i) {
                around(&p,i*4096u,0);
                around(&p,i*4096u+((i&1)?swing*4096u/50u:0),0);
            }
            process(&p,EUL_PHASE-1,0,0,0); process(&p,0,0,0,0);
            for(unsigned i=n;i-->0;) {
                uint32_t at=phase_at(i*4096u+((i&1)?swing*4096u/50u:0),n);
                process(&p,at+1,0,0,0); process(&p,at,0,0,0);
                if(at) process(&p,at-1,0,0,0);
            }
            process(&p,EUL_PHASE-1,0,0,0); process(&p,0,1,0,0);
            process(&p,EUL_PHASE/2,0,1,0); process(&p,EUL_PHASE,0,0,0);
        }
}

static void envelope_edges(void) {
    section="all attack/decay values and envelope/gate edges";
    EulParams p={16,1,0,0,0,0,1,0,127,0};
    for(unsigned mode=0;mode<8;++mode) for(unsigned attack=0;attack<128;++attack)
        for(unsigned decay=0;decay<128;++decay) {
            p.mode=mode; p.attack=attack; p.decay=decay;
            unsigned a=4096u*attack*attack/16129u;
            unsigned tail=decay-63u;
            unsigned d=decay<64?(decay+1u)*(decay+1u):4096u+7u*tail*tail;
            unsigned length=(decay+1u)*32u,edge=a<length/2?a:length/2;
            clear_states(); process(&p,0,1,0,3);
            around(&p,a,3); around(&p,a+d,3);
            around(&p,length,3); around(&p,edge,3);
            around(&p,length+edge,3);
            process(&p,EUL_PHASE-1,0,0,3); process(&p,0,0,0,3);
        }
}

static void dense_curves(void) {
    section="every quantized attack and decay age";
    EulParams p={16,1,0,EUL_ENV,0,0,0,0,127,0};
    for(unsigned attack=0;attack<128;++attack) {
        p.attack=attack; p.decay=127;
        unsigned duration=4096u*attack*attack/16129u;
        for(unsigned mode=0;mode<4;++mode) {
            p.mode=mode; clear_states();
            for(unsigned age=0;age<=duration+1;++age)
                process(&p,phase_at(age,16),0,0,attack%48);
            /* Start another hit with nonzero origin for random interpolation. */
            process(&p,EUL_PHASE-1,0,0,attack%48);
            for(unsigned age=0;age<=duration+1;++age)
                process(&p,phase_at(age,16),0,0,attack%48);
        }
    }
    p.mode=EUL_ENV; p.attack=0;
    for(unsigned decay=0;decay<128;++decay) {
        p.decay=decay;
        unsigned tail=decay-63u;
        unsigned duration=decay<64?(decay+1u)*(decay+1u):4096u+7u*tail*tail;
        clear_states();
        for(unsigned age=0;age<=duration+1;++age)
            process(&p,phase_at(age,16),0,0,decay%48);
    }
    section="all accent boosts across envelope levels and both polarities";
    p.accents=1; p.attack=127; p.decay=127;
    for(unsigned boost=0;boost<128;++boost) {
        p.boost=boost;
        for(unsigned mode=0;mode<8;++mode) {
            p.mode=mode; clear_states();
            for(unsigned age=0;age<4096;++age)
                process(&p,phase_at(age,16),0,0,boost%48);
        }
    }
}

static void edits_and_malformed(void) {
    section="malformed/default params and saturating edits";
    EulParams expected,actual;
    baseline_eul_defaults(&expected); eul_defaults(&actual);
    if(memcmp(&actual,&expected,sizeof(actual))) mismatch("defaults",1,0);
    const int deltas[]={-2147483647-1,-128,-127,-1,0,1,127,128,2147483647};
    for(unsigned field=0;field<sizeof(EulParams);++field)
        for(unsigned value=0;value<256;++value) {
            EulParams p;
            eul_defaults(&p); ((uint8_t *)&p)[field]=value;
            actual=expected=p;
            eul_normalize(&actual); baseline_eul_normalize(&expected);
            if(memcmp(&actual,&expected,sizeof(actual))) mismatch("normalize",1,0);
            masks(&p); clear_states();
            for(unsigned phase=0;phase<7;++phase)
                process(&p,phase*EUL_PHASE/6u,phase==0,phase==5,47);
            for(unsigned edited=0;edited<=12;++edited)
                for(unsigned d=0;d<sizeof(deltas)/sizeof(deltas[0]);++d) {
                    actual=expected=p;
                    unsigned changed=eul_edit(&actual,edited,deltas[d]);
                    unsigned old_changed=baseline_eul_edit(&expected,edited,deltas[d]);
                    ++edit_cases;
                    EQUAL("edit changed",changed,old_changed);
                    if(memcmp(&actual,&expected,sizeof(actual))) mismatch("edit bytes",1,0);
                }
        }
}

static void random_events(void) {
    section="deterministic live edits, mode/DIR changes, skips, wraps and resets";
    for(unsigned identity=0;identity<48;++identity) {
        EulParams p;
        eul_defaults(&p); clear_states();
        uint32_t phase=0;
        for(unsigned event=0;event<12000;++event) {
            uint32_t action=next_random();
            if((action&31)==0) {
                /* Include simultaneous malformed bytes, not only valid UI values. */
                for(unsigned i=0;i<sizeof(p);++i) ((uint8_t *)&p)[i]=next_random()>>24;
            } else if((action&7)==0) {
                eul_edit(&p,next_random()%11,(int)(next_random()%255)-127);
            } else if((action&15)==1) {
                p.mode^=EUL_NEGATIVE;
            } else if((action&15)==2) {
                p.mode=(p.mode&EUL_NEGATIVE)|(event&3);
            }
            switch((action>>8)&7) {
            case 0: phase=next_random()%EUL_PHASE; break;
            case 1: phase=(phase-1u)&(EUL_PHASE-1); break;
            case 2: phase=(phase-((action>>16)&65535))&(EUL_PHASE-1); break;
            case 3: phase=(phase+1)&(EUL_PHASE-1); break;
            case 4: phase=(phase+((action>>16)&65535))&(EUL_PHASE-1); break;
            case 5: phase=0; break;
            case 6: phase=EUL_PHASE-1; break;
            default: break; /* STOP/no movement must not advance RNG. */
            }
            process(&p,phase,(action>>12)%97==0,(action>>20)%113==0,identity);
        }
    }
    section="RAND to LOOP preserves full random history";
    for(unsigned steps=1;steps<=16;++steps) for(unsigned rotate=0;rotate<steps;++rotate) {
        EulParams p={steps,steps,rotate,EUL_RAND,127,127,steps/2,0,127,30};
        clear_states();
        for(unsigned i=0;i<steps*4;++i) process(&p,(i%steps)*EUL_PHASE/steps,0,0,17);
        p.mode=EUL_LOOP;
        for(unsigned i=0;i<steps*4;++i) process(&p,(i%steps)*EUL_PHASE/steps,0,0,17);
        p.mode|=EUL_NEGATIVE;
        for(unsigned i=steps*4;i-->0;) process(&p,(i%steps)*EUL_PHASE/steps,0,0,17);
    }
}

static void clocks(void) {
    section="native clock exact outputs and signed carry";
    const int32_t increments[]={-67108863,-524289,-65537,-1,0,1,65537,524289,67108863};
    for(unsigned steps=1;steps<=16;++steps) {
        int32_t actual_carry=0,expected_carry=0;
        for(unsigned i=0;i<10000;++i) {
            int32_t increment=increments[next_random()%(sizeof(increments)/sizeof(increments[0]))];
            int32_t actual=eul_clock(increment,steps,&actual_carry);
            int32_t expected=baseline_eul_clock(increment,steps,&expected_carry);
            ++clock_cases; EQUAL("native clock",actual,expected);
            EQUAL("native residue",actual_carry,expected_carry);
        }
    }
    section="cached audio clock all signed speeds and live context changes";
    const unsigned tempos[]={0,1,720,2880,8191};
    EulAudioClock cache={0};
    for(unsigned steps=1;steps<=16;++steps) for(unsigned mult=0;mult<=6;++mult) {
        int32_t actual_carry=0,expected_carry=0,uncached_carry=0;
        for(int speed=-32768;speed<=32767;++speed) {
            unsigned tempo=tempos[((unsigned)speed+32768)%5];
            int32_t actual=eul_audio_clock_cached(&cache,speed,tempo,mult,steps,&actual_carry);
            int32_t expected=baseline_eul_audio_clock(speed,tempo,mult,steps,&expected_carry);
            int32_t uncached=eul_audio_clock(speed,tempo,mult,steps,&uncached_carry);
            ++clock_cases; EQUAL("cached audio clock",actual,expected);
            EQUAL("audio residue",actual_carry,expected_carry);
            EQUAL("uncached audio clock",uncached,expected);
            EQUAL("uncached residue",uncached_carry,expected_carry);
        }
    }
    /* Force cache hits, reversals with nonzero opposite-sign carry, tempo and
     * MULT modulation; reset only at the caller-owned STEPS context change. */
    int32_t actual_carry=0,expected_carry=0;
    unsigned steps=7,tempo=2880,mult=1;
    int speed=16384;
    for(unsigned i=0;i<200000;++i) {
        uint32_t action=next_random();
        if((action&63)==0) { steps=1+next_random()%16; actual_carry=expected_carry=0; }
        if((action&15)==0) speed=(int)(next_random()&65535)-32768;
        if((action&31)==1) tempo=next_random()%8192;
        if((action&31)==2) mult=next_random()%7;
        int32_t actual=eul_audio_clock_cached(&cache,speed,tempo,mult,steps,&actual_carry);
        int32_t expected=baseline_eul_audio_clock(speed,tempo,mult,steps,&expected_carry);
        ++clock_cases; EQUAL("modulated audio clock",actual,expected);
        EQUAL("modulated residue",actual_carry,expected_carry);
    }
}

int main(int argc,char **argv) {
    negative_control=argc==2 && !strcmp(argv[1],"--negative-control");
    exhaustive_masks(); timing_edges(); envelope_edges(); dense_curves();
    edits_and_malformed(); random_events(); clocks();
    printf("bit-exact Euclid equivalence passed: %lu process, %lu masks, "
           "%lu clocks, %lu edits\n",process_cases,mask_cases,clock_cases,edit_cases);
    return 0;
}
#endif
