/* Independent adaptation of modules/euclid/control.c's pulse distribution,
 * xorshift random source and envelope curves. This module does not depend on
 * the EUCLID effect. Native LFO phase replaces its track-clock scheduler.
 * All products fit 32 bits; no floating point or runtime library calls. */
#include "engine.h"

int32_t eul_clock(int32_t increment, unsigned steps, int32_t *remainder) {
    int32_t numerator=increment*16+*remainder;
    int32_t result=numerator/(int32_t)steps;
    *remainder=numerator-result*(int32_t)steps;
    return result;
}

int32_t eul_audio_clock(int speed, unsigned tempo, unsigned mult,
                        unsigned steps, int32_t *remainder) {
    /* Exact rational: speed*tempo*8*(16<<mult)/(496125*steps).
     * Split before multiplying so even -32768 SPD, tempo 8191, MULT64
     * fit signed 32 bits. No 64-bit divide helper in the frame interrupt.
     * 496125 = 44100*45/4. At SPD64/MULT2, each step is one sixteenth
     * at 16 samples/frame, independently of the pattern length. */
    int32_t base=speed*(int32_t)(tempo*8);
    int32_t whole=base/496125, fraction=base-whole*496125;
    int32_t scale=16<<mult, scaled=whole*scale;
    int32_t result=scaled/(int32_t)steps;
    int32_t numerator=(scaled-result*(int32_t)steps)*496125
                      +fraction*scale+*remainder;
    int32_t denominator=496125*(int32_t)steps;
    int32_t extra=numerator/denominator;
    *remainder=numerator-extra*denominator;
    return result+extra;
}

_Static_assert(sizeof(EulParams) == 10, "version 1 settings payload");
static unsigned min_u(unsigned a, unsigned b) { return a < b ? a : b; }
static uint32_t random_value(uint32_t *state) {
    uint32_t x = *state;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    *state = x;
    return x >> 17;
}
void eul_defaults(EulParams *p) {
    p->steps=8; p->pulses=3; p->rotate=0; p->mode=EUL_ENV;
    p->attack=0; p->decay=48;
    p->accents=0; p->accent_rotate=0; p->boost=64; p->swing=0;
}
void eul_normalize(EulParams *p) {
    if (!p->steps) { eul_defaults(p); return; }
    p->steps=min_u(p->steps, EUL_STEPS);
    p->pulses=min_u(p->pulses, p->steps);
    p->rotate=min_u(p->rotate, p->steps-1);
    p->mode=min_u(p->mode, EUL_LOOP|EUL_NEGATIVE);
    p->attack=min_u(p->attack,127); p->decay=min_u(p->decay,127);
    p->accents=min_u(p->accents,p->pulses);
    p->accent_rotate=p->pulses ? min_u(p->accent_rotate,p->pulses-1) : 0;
    p->boost=min_u(p->boost,127); p->swing=min_u(p->swing,30);
}
void eul_masks(const EulParams *raw, uint16_t *hits, uint16_t *accents) {
    EulParams p=*raw;
    eul_normalize(&p);
    unsigned h=0,a=0;
    if(p.pulses) {
        /* Equivalent to (i*k)%n<k, with bounded accumulators instead of
         * repeated hardware divisions. Accents advance only on pulses. */
        unsigned phase=0,ap=((p.pulses-p.accent_rotate)*p.accents)%p.pulses;
        unsigned at=p.rotate;
        for(unsigned i=0;i<p.steps;++i) {
            if(phase<p.pulses) {
                h|=1u<<at;
                if(ap<p.accents) a|=1u<<at;
                ap+=p.accents;
                if(ap>=p.pulses) ap-=p.pulses;
            }
            phase+=p.pulses;
            if(phase>=p.steps) phase-=p.steps;
            if(++at==p.steps) at=0;
        }
    }
    *hits=(uint16_t)h; *accents=(uint16_t)a;
}
unsigned eul_edit(EulParams *p, unsigned field, int delta) {
    if (field>EUL_DIRECTION_FIELD || !delta) return 0;
    EulParams before=*p;
    eul_normalize(p);
    uint8_t *bytes=(uint8_t *)p;
    unsigned maxima[]={16,p->steps,p->steps-1,3,127,127,p->pulses,
                       p->pulses ? p->pulses-1 : 0,127,30,1};
    /* The panel delivers signed bytes; clamp anyway for hostile test input. */
    if (delta>127) delta=127;
    if (delta< -127) delta=-127;
    unsigned old=field==EUL_DIRECTION_FIELD ? !!(p->mode&EUL_NEGATIVE)
        : field==3 ? p->mode&EUL_SHAPE_MASK : bytes[field];
    int value=(int)old+delta, low=field==0 ? 1 : 0;
    if (value<low) value=low;
    if (value>(int)maxima[field]) value=(int)maxima[field];
    if(field==EUL_DIRECTION_FIELD) p->mode=(p->mode&EUL_SHAPE_MASK)|(value?EUL_NEGATIVE:0);
    else if(field==3) p->mode=(p->mode&EUL_NEGATIVE)|(uint8_t)value;
    else bytes[field]=(uint8_t)value;
    eul_normalize(p);
    for (unsigned i=0;i<sizeof(*p);++i)
        if (((uint8_t *)&before)[i]!=bytes[i]) return 1;
    return 0;
}
static unsigned same(const EulParams *a, const EulParams *b) {
    for (unsigned i=0;i<sizeof(*a);++i)
        /* Direction changes the final sign only, never a random target. */
        if ((((const uint8_t *)a)[i]^((const uint8_t *)b)[i]) & (i==3?EUL_SHAPE_MASK:255)) return 0;
    return 1;
}
static unsigned same_source(const EulParams *a, const EulParams *b) {
    for(unsigned i=0;i<sizeof(*a);++i)
        if(((const uint8_t *)a)[i]!=((const uint8_t *)b)[i]) return 0;
    return 1;
}
static uint32_t interpolate(uint32_t from, uint32_t to, unsigned age,
                             unsigned duration) {
    if (!duration || age>=duration) return to;
    if (to>=from) return from+(to-from)*age/duration;
    return from-(from-to)*age/duration;
}
int32_t eul_process(EulState *s, const EulParams *raw, uint32_t phase,
                    unsigned reset, unsigned terminal, unsigned identity) {
    /* Normalize and derive coefficients only when the ten source bytes
     * change. The cache is per LFO, including absent/malformed records.
     * Nothing derived is persisted or borrowed from native LFO memory. */
    if(!s->ready || !same_source(raw,&s->source)) {
        EulParams p=*raw;
        eul_normalize(&p);
        if (!s->ready) {
            s->rng=0x6d2b79f5u ^ (0x9e3779b9u*(identity+1));
            if (!s->rng) s->rng=1;
            for (unsigned i=0;i<EUL_STEPS;++i) s->values[i]=random_value(&s->rng);
            s->level=s->origin=s->target=0;
            s->last_hit=255; s->phase=0;
        }
        if (!s->ready || !same(&p,&s->params)) {
            eul_masks(&p,&s->hits,&s->accents);
            /* Two linear scans, rather than walking backwards separately
             * for every step (quadratic for a sparse 16-step rhythm). */
            unsigned previous=0,delay=p.swing*4096u/50u;
            for(unsigned i=0;i<p.steps;++i) if(s->hits&(1u<<i)) previous=i;
            for(unsigned i=0;i<p.steps;++i) {
                if(s->hits&(1u<<i)) previous=i;
                s->previous[i]=(uint8_t)previous;
                s->boundaries[i]=(uint16_t)(i*4096u+((i&1)?delay:0));
            }
            s->attack=4096u*p.attack*p.attack/16129u;
            if(p.decay<64) s->decay=(p.decay+1u)*(p.decay+1u);
            else { unsigned tail=p.decay-63u; s->decay=4096u+7u*tail*tail; }
            s->length=(p.decay+1u)*32u;
            s->edge=min_u(s->attack,s->length/2);
            /* Edits/mode changes must not reuse a stale random target.
             * DIR alone deliberately leaves it intact. */
            s->last_hit=255;
        }
        s->source=*raw;
        s->params=p;
        s->ready=1;
    }
    const EulParams *p=&s->params;
    unsigned mode=p->mode&EUL_SHAPE_MASK;
    if (terminal || phase>=EUL_PHASE || !p->pulses) {
        s->level=s->origin=s->target=0; s->last_hit=255;
        s->phase=phase;
        return 0;
    }
    unsigned position=(phase*p->steps)>>11;
    unsigned step=position>>12;
    if ((step&1) && position<s->boundaries[step]) --step;
    unsigned hit=s->previous[step], at=s->boundaries[hit];
    unsigned age=position>=at ? position-at : position+p->steps*4096u-at;
    unsigned attack=s->attack;
    unsigned wrap=(phase>s->phase ? phase-s->phase : s->phase-phase)>EUL_PHASE/2;
    unsigned previous_position=(s->phase*p->steps)>>11;
    unsigned crossed=wrap ? (phase<s->phase
        ? (at<=position || at>previous_position)
        : (at>=position || at<previous_position))
        : (phase>=s->phase ? (previous_position<at && at<=position)
                          : (position<=at && at<previous_position));
    if (reset) { s->last_hit=255; s->level=0; }
    if (s->last_hit!=hit || crossed) {
        s->origin=s->level;
        unsigned index=(hit+p->steps-p->rotate)%p->steps;
        if (mode==EUL_RAND) s->values[index]=(uint16_t)random_value(&s->rng);
        s->target=s->values[index];
        s->last_hit=(uint8_t)hit;
    }
    s->phase=phase; s->last_step=(uint8_t)step;
    if (mode==EUL_ENV) {
        if (age<attack) s->level=interpolate(0,EUL_LEVEL,age,attack);
        else {
            unsigned ramp=interpolate(EUL_LEVEL,0,age-attack,s->decay);
            s->level=ramp*ramp/EUL_LEVEL;
        }
    } else if (mode==EUL_GATE) {
        unsigned length=s->length,edge=s->edge;
        s->level=age<length ? interpolate(0,EUL_LEVEL,age,edge)
                           : interpolate(EUL_LEVEL,0,age-length,edge);
    } else s->level=interpolate(s->origin,s->target,age,attack);
    unsigned level=s->level;
    if (s->accents&(1u<<hit)) level+=level*p->boost/127u;
    int32_t output=(int32_t)(level<<8);
    return p->mode&EUL_NEGATIVE ? -output : output;
}
