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
static int32_t ss_mul(int32_t a,int32_t b) { return (a*b)>>14; }
/* Exact floor of a*b/16384 for the wider HP intermediate, without int64. */
static int32_t ss_wide_mul(int32_t a,int32_t b) {
    /* b is nonnegative and < 65536: the low product stays below 2^30.
     * Splitting at the final Q14 boundary removes a shift from every MAC. */
    return (a>>14)*b+(((a&16383)*b)>>14);
}
/* Specialize the fully wet, fixed-coefficient loops at compile time. The
 * changing-coefficient/bypass path keeps the same sample-wise arithmetic.
 * Keep integrator state in locals rather than writing DRAM every sample. */
static __attribute__((always_inline)) inline void ss_filter_block(
        struct ss_filter *s,int16_t *audio,unsigned n,unsigned shape,unsigned steady,
        unsigned enabled,int32_t d1,int32_t d2,int32_t d3) {
    int32_t s0=s->s0,s1=s->s1,a1=s->a1,a2=s->a2,a3=s->a3;
    unsigned wet=s->wet;
    for(unsigned i=0;i<n;++i) {
        if(!steady) { a1+=d1;a2+=d2;a3+=d3; }
        int32_t x=(int32_t)audio[i]*256;
        int32_t hp=ss_limit(ss_wide_mul(x-ss_wide_mul(s0,a3)-s1,a1));
        int32_t v=ss_wide_mul(hp,a2),bp=ss_limit(s0+v);
        s0=ss_limit(s0+2*v);
        int32_t q=ss_wide_mul(bp,a2),lp=ss_limit(s1+q);
        s1=ss_limit(s1+2*q);
        int32_t y=shape==1?lp:shape==2?bp:hp;
        if(steady) audio[i]=(int16_t)(y>>8);
        else {
            if(enabled) { if(wet<128)++wet; } else if(wet)--wet;
            audio[i]=(int16_t)((wet==128?y:x+((y-x)*(int32_t)wet)/128)>>8);
        }
    }
    s->s0=s0;s->s1=s1;s->wet=(uint16_t)wet;
}
void ss_filter_run(struct ss_filter *s,const struct ss_filter_params *p,
                          uint32_t stamp,int16_t *audio,unsigned n) {
    if (!n) return;
    unsigned type=p->type<=3?p->type:0;
    if (!type && !s->wet) { s->ready=0; s->stamp=stamp; return; }
    if (!s->ready || !s->wet) {
        s->s0=s->s1=0;s->envelope=0;s->ready=1;s->stamp=stamp-1;
    }
    if (s->stamp!=stamp) { s->envelope=1u<<24;s->stamp=stamp; }
    unsigned cutoff=(p->cutoff&127)+(((s->envelope>>12)*(p->amount&127))>>12);
    if(cutoff>127)cutoff=127;
    int32_t g=ss_filter_g[cutoff];
    /* Spectrum: damping=(0.998 - (RES/128)*0.587)^4. */
    int32_t k=ss_filter_damping[p->resonance&127];
    int32_t a1=s->a1,a2=g,a3=k+g;
    int32_t d1=0,d2=0,d3=0;
    if(!s->wet || g!=s->a2 || k!=s->damping) {
        int32_t den=16384+ss_mul(k,g)+ss_mul(g,g);
        a1=268435456/den;
        if(s->wet) {
            d1=(a1-s->a1)/(int)n;d2=(a2-s->a2)/(int)n;d3=(a3-s->a3)/(int)n;
        } else { s->a1=a1;s->a2=a2;s->a3=a3; }
    }
    if(type)s->type=(uint8_t)type;
    if(type && s->wet==128 && !(d1|d2|d3)) {
        if(type==1)ss_filter_block(s,audio,n,1,1,1,0,0,0);
        else if(type==2)ss_filter_block(s,audio,n,2,1,1,0,0,0);
        else ss_filter_block(s,audio,n,3,1,1,0,0,0);
    } else ss_filter_block(s,audio,n,s->type,0,type,d1,d2,d3);
    /* Envelope only affects the next block's coefficients. Updating this
     * local separately is bit-identical and avoids inner-loop state spills. */
    uint32_t envelope=s->envelope;
    if(envelope) {
        unsigned fall=ss_filter_decay[p->decay&127];
        for(unsigned i=0;i<n && envelope;++i) {
            uint32_t drop=((envelope>>8)*fall)>>8;
            envelope-=drop?drop:1;
        }
    }
    s->envelope=envelope;
    s->a1=a1;s->a2=a2;s->a3=a3;s->damping=k;
}
#endif
