/* SPDX-License-Identifier: MIT
 * Mono TPT SEM/SVF, adapted from Spectrum's documented Zavalishin equations.
 * Spectrum by sambanks; mathematical design reference: audiojs/filter (MIT).
 * Q14 coefficients, 24-bit bounded signed states; no float or 64-bit runtime helpers.
 */
#ifndef SS_FILTER_H
#define SS_FILTER_H
struct ss_filter {
    int32_t s0, s1, a1, a2, a3, damping;
    uint32_t envelope, stamp;
    uint16_t wet;
    uint8_t type, ready;
};
struct ss_filter_params { uint8_t cutoff, resonance, amount, decay, type; };
static void ss_filter_reset(struct ss_filter *s) {
    s->s0=s->s1=s->a1=s->a2=s->a3=s->damping=0;
    s->envelope=s->stamp=0;s->wet=0;s->type=s->ready=0;
}
static int32_t ss_limit(int32_t x) { return x>8388607?8388607:x< -8388607?-8388607:x; }
/* Exact floor of a*b/16384 for the wider HP intermediate, without int64. */
static inline int32_t ss_wide_mul(int32_t a,int32_t b) {
    /* b is nonnegative and < 131072: the low product stays below 2^31.
     * Splitting at the final Q14 boundary removes a shift from every MAC. */
    return (a>>14)*b+(((a&16383)*b)>>14);
}
/* ColdFire's fractional EMAC performs floor(a*b/2^31). Scale the signed
 * input by 16 and each Q14 coefficient by 8192 to retain the exact Q14
 * product. The widest half-rate HP input is bounded by 53,362,171 and
 * the largest coefficient by 71,455, so both scaled operands fit int32.
 * Keep scaled coefficients/deltas in loop locals, never persisted state. */
static inline int32_t ss_filter_coefficient(int32_t b) {
#ifdef __m68k__
    return b*8192;
#else
    return b;
#endif
}
static inline int32_t ss_filter_mul(int32_t a,int32_t b) {
#ifdef __m68k__
    int32_t result;
    __asm__ volatile ("mac.l %1,%2,%%acc0\n\tmovclr.l %%acc0,%0"
        : "=d"(result) : "d"(a*16), "d"(b) : "cc");
    return result;
#else
    return ss_wide_mul(a,b);
#endif
}
#ifdef __m68k__
struct ss_emac_state { uint32_t status,accumulator,extension; };
static inline struct ss_emac_state ss_filter_enter(void) {
    struct ss_emac_state s;
    /* Integer mode reads raw accumulator bits without fractional rounding
     * or saturation, matching the stock frame ISR's save/restore idiom.
     * ACCEXT01 includes acc1's extension too; it is restored unchanged. */
    __asm__ volatile ("move.l %%macsr,%0\n\tmove.l #0,%%macsr\n\t"
        "move.l %%acc0,%1\n\tmove.l %%accext01,%2\n\t"
        "move.l #32,%%macsr\n\tmove.l #0,%%acc0"
        : "=d"(s.status),"=d"(s.accumulator),"=d"(s.extension)
        :: "memory","cc");
    return s;
}
static inline void ss_filter_leave(struct ss_emac_state s) {
    __asm__ volatile ("move.l #0,%%macsr\n\tmove.l %1,%%acc0\n\t"
        "move.l %2,%%accext01\n\tmove.l %0,%%macsr"
        :: "d"(s.status),"d"(s.accumulator),"d"(s.extension)
        : "memory","cc");
}
#endif
/* Specialize the fully wet, fixed-coefficient loops at compile time. The
 * changing-coefficient/bypass path keeps the same sample-wise arithmetic.
 * Keep integrator state in locals rather than writing DRAM every sample. */
static __attribute__((always_inline)) inline void ss_filter_block(
        struct ss_filter *s,int16_t *audio,unsigned n,unsigned shape,unsigned steady,
        unsigned enabled,unsigned rate,int32_t d1,int32_t d2,int32_t d3) {
    int32_t s0=s->s0,s1=s->s1,a1=s->a1,a2=s->a2,a3=s->a3;
    a1=ss_filter_coefficient(a1);a2=ss_filter_coefficient(a2);a3=ss_filter_coefficient(a3);
    d1=ss_filter_coefficient(d1);d2=ss_filter_coefficient(d2);d3=ss_filter_coefficient(d3);
    unsigned wet=s->wet;
    for(unsigned i=0;i<n;++i) {
        if(!steady) { a1+=d1;a2+=d2;a3+=d3; }
        int32_t x=(int32_t)audio[i]*256;
        int32_t hp=ss_limit(ss_filter_mul(x-ss_filter_mul(s0,a3)-s1,a1));
        int32_t v=ss_filter_mul(hp,a2),bp=ss_limit(s0+v);
        s0=ss_limit(s0+2*v);
        int32_t q=ss_filter_mul(bp,a2),lp=ss_limit(s1+q);
        s1=ss_limit(s1+2*q);
        int32_t y=shape==1?lp:shape==2?bp:hp;
        if(steady || enabled==4) audio[i]=(int16_t)(y>>8);
        else {
            if(enabled) { if(wet<128)wet=wet+rate>128?128:wet+rate; } else if(wet)wet=wet>rate?wet-rate:0;
            audio[i]=(int16_t)((wet==128?y:x+((y-x)*(int32_t)wet)/128)>>8);
        }
    }
    s->s0=s0;s->s1=s1;s->wet=(uint16_t)wet;
}
/* Signed division truncates toward zero. Native blocks are 16 samples;
 * keep split/short calls exact and avoid three hardware divides per voice. */
static int32_t ss_filter_step(int32_t delta,unsigned n) {
    if(n==8)return delta<0 ? -((-delta)>>3) : delta>>3;
    if(n==16)return delta<0 ? -((-delta)>>4) : delta>>4;
    if(n==32)return delta<0 ? -((-delta)>>5) : delta>>5;
    if(n==1)return delta;
    return delta/(int)n;
}
static __attribute__((always_inline)) inline void ss_filter_impl(struct ss_filter *s,const struct ss_filter_params *p,
                          uint32_t stamp,int16_t *audio,unsigned n,unsigned rate) {
    if (!n) return;
    unsigned type=p->type<=3?p->type:0;
    if (!type && !s->wet) { s->ready=0; s->stamp=stamp; return; }
    if (!s->ready || !s->wet) {
        s->s0=s->s1=0;s->envelope=0;s->ready=1;s->stamp=stamp-1;
    }
    if (s->stamp!=stamp) { s->envelope=1u<<24;s->stamp=stamp; }
    unsigned cutoff=(p->cutoff&127)+(((s->envelope>>12)*(p->amount&127))>>12);
    if(cutoff>127)cutoff=127;
    int32_t g=rate==2?ss_filter_half_g[cutoff]:ss_filter_g[cutoff];
    /* Spectrum: damping=(0.998 - (RES/128)*0.587)^4. */
    int32_t k=ss_filter_damping[p->resonance&127];
    int32_t a1=s->a1,a2=g,a3=k+g;
    int32_t d1=0,d2=0,d3=0;
    if(!s->wet || g!=s->a2 || k!=s->damping) {
        a1=rate==2?ss_filter_half_a1[p->resonance&127][cutoff]:ss_filter_a1[p->resonance&127][cutoff];
        if(s->wet) {
            d1=ss_filter_step(a1-s->a1,n);d2=ss_filter_step(a2-s->a2,n);d3=ss_filter_step(a3-s->a3,n);
        } else { s->a1=a1;s->a2=a2;s->a3=a3; }
    }
    if(type)s->type=(uint8_t)type;
    if(type && s->wet==128 && !(d1|d2|d3)) {
        if(type==1)ss_filter_block(s,audio,n,1,1,1,rate,0,0,0);
        else if(type==2)ss_filter_block(s,audio,n,2,1,1,rate,0,0,0);
        else ss_filter_block(s,audio,n,3,1,1,rate,0,0,0);
    } else if(type && s->wet==128) {
        /* A moving cutoff does not require a bypass crossfade or per-sample
         * mode selection. Keep three fixed-output, fully-wet ramp loops. */
        if(type==1)ss_filter_block(s,audio,n,1,0,4,rate,d1,d2,d3);
        else if(type==2)ss_filter_block(s,audio,n,2,0,4,rate,d1,d2,d3);
        else ss_filter_block(s,audio,n,3,0,4,rate,d1,d2,d3);
    } else ss_filter_block(s,audio,n,s->type,0,type,rate,d1,d2,d3);
    /* Envelope only affects the next block's coefficients. Updating this
     * local separately is bit-identical and avoids inner-loop state spills. */
    uint32_t envelope=s->envelope;
    if(envelope) {
        unsigned fall=ss_filter_decay[p->decay&127];
        if(rate==2) {
            /* The envelope only drives block-rate coefficients. Advance it
             * once for the elapsed output samples, even while ENV is zero,
             * so enabling ENV mid-note does not resurrect a stale attack. */
            fall=ss_filter_half_decay[n][p->decay&127];
            uint32_t drop=((envelope>>8)*fall)>>8;
            envelope-=drop?drop:1;
            /* Below this level no ENV value can change an integer CUT. */
            if(envelope<33u*4096)envelope=0;
        } else for(unsigned i=0;i<n && envelope;++i) {
            uint32_t drop=((envelope>>8)*fall)>>8;
            envelope-=drop?drop:1;
        }
    }
    s->envelope=envelope;
    s->a1=a1;s->a2=a2;s->a3=a3;s->damping=k;
}
#ifdef SS_HOST_TEST
void ss_filter_run(struct ss_filter *s,const struct ss_filter_params *p,
                   uint32_t stamp,int16_t *audio,unsigned n) {
    if(!n)return;
    if((p->type<1 || p->type>3) && !s->wet) { s->ready=0;s->stamp=stamp;return; }
#ifdef __m68k__
    struct ss_emac_state saved=ss_filter_enter();
#endif
    ss_filter_impl(s,p,stamp,audio,n,1);
#ifdef __m68k__
    ss_filter_leave(saved);
#endif
}
#endif
static __attribute__((noinline,aligned(16))) void ss_filter_half(struct ss_filter *s,const struct ss_filter_params *p,
                           uint32_t stamp,int16_t *audio,unsigned n) {
    if(!n)return;
    if((p->type<1 || p->type>3) && !s->wet) { s->ready=0;s->stamp=stamp;return; }
#ifdef __m68k__
    struct ss_emac_state saved=ss_filter_enter();
#endif
    ss_filter_impl(s,p,stamp,audio,n,2);
#ifdef __m68k__
    ss_filter_leave(saved);
#endif
}
#endif
