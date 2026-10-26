/* Fixed-capacity storage: 85 degree states times 9 CHRD states fit 10 bits.
 * HARM publications use a canonical native mirror, so the exact edit
 * snapshot is reconstructed from DEG. Non-HARM snapshots are never used
 * for edit detection. No sparse overflow, journal or capacity reduction.
 * Each lane starts with state*84+scale, followed by MSB-first tokens.
 * Exact snapshots are essential: KEY changes preserve DEG, whereas a native
 * NOTE edit since the checkpoint must be detected, including after reboot. */
#include "packed.h"

static inline int token(const HdRoots *r, unsigned step, unsigned q) {
    unsigned d = r->degree[step], n = r->note[step];
    if ((d >= HD_CODES && d != HD_NONE) || (q > 7 && q != HD_NONE)) return -1;
    if (r->state == HD_ROOT_HARM) {
        if (n != hd_mirror_c(d)) return -1;
    } else if (d != HD_NONE || (n > 127 && n != HD_NONE) ||
               (r->state == HD_ROOT_UNKNOWN && n != HD_NONE)) return -1;
    return (int)((d == HD_NONE ? 84u : d) * 9u + (q == HD_NONE ? 8u : q));
}

int hd_pack_c(const HdBank *bank, const uint8_t *qualities, volatile uint8_t *p) {
    for (unsigned lane = 0; lane < HD_LANES; ++lane) {
        const HdRoots *r = &bank->roots[lane];
        /* Validate metadata here and step data while constructing tokens.
         * HARM's canonical mirror check also proves NOTE range/sentinel
         * validity, avoiding a separate full hd_roots_valid_c lane scan. */
        if (r->state > HD_ROOT_HARM || r->scale >= 84 ||
            (r->context >= 64 && r->context != HD_NONE) ||
            (r->state == HD_ROOT_UNKNOWN && r->context != HD_NONE)) return 0;
        *p++ = (uint8_t)(r->state * 84u + r->scale);
        /* Four ten-bit tokens always occupy five bytes. The format is
         * unchanged; no per-token reservoir or variable shift loop. */
        for (unsigned step = 0; step < HD_STEPS; step += 4) {
            int a = token(r,step,qualities[0]), b = token(r,step+1,qualities[1]);
            int c = token(r,step+2,qualities[2]), d = token(r,step+3,qualities[3]);
            if ((a | b | c | d) < 0) return 0;
            p[0] = (uint8_t)((unsigned)a >> 2);
            p[1] = (uint8_t)(((unsigned)a << 6) | ((unsigned)b >> 4));
            p[2] = (uint8_t)(((unsigned)b << 4) | ((unsigned)c >> 6));
            p[3] = (uint8_t)(((unsigned)c << 2) | ((unsigned)d >> 8));
            p[4] = (uint8_t)d;
            p += 5;
            qualities += 4;
        }
    }
    return 1;
}

/* Validation needs only the token bounds, not division into degree/quality.
 * Every 0..764 token is legal in HARM; other states allow 756..764 only.
 * Four fixed ten-bit fields avoid a per-token reservoir and refill branch. */
int hd_packed_valid_c(const volatile uint8_t *p) {
    for (unsigned lane=0; lane<HD_LANES; ++lane) {
        unsigned meta=*p++, minimum=meta<168 ? 756u : 0u;
        if (meta>=252) return 0;
        for (unsigned step=0; step<HD_STEPS; step+=4,p+=5) {
            unsigned a=(unsigned)p[0]<<2 | p[1]>>6;
            unsigned b=((unsigned)p[1]&63u)<<4 | p[2]>>4;
            unsigned c=((unsigned)p[2]&15u)<<6 | p[3]>>2;
            unsigned d=((unsigned)p[3]&3u)<<8 | p[4];
            if (a<minimum || a>764 || b<minimum || b>764 ||
                c<minimum || c>764 || d<minimum || d>764) return 0;
        }
    }
    return 1;
}
static inline void publish(HdRoots *r, uint8_t *qualities, unsigned step, unsigned token) {
    /* Exactly floor(token/9) for validated 0..764 tokens. The bounded
     * reciprocal avoids ColdFire long division and remainder per step. */
    unsigned d=(token*911u)>>13, q=token-d*9u;
    if (d==84) d=HD_NONE;
    if (r) { r->degree[step]=(uint8_t)d; r->note[step]=(uint8_t)hd_mirror_c(d); }
    if (qualities) qualities[step]=(uint8_t)(q==8 ? HD_NONE : q);
}
int hd_unpack_c(HdBank *bank, uint8_t *qualities, const volatile uint8_t *p) {
    if (!hd_packed_valid_c(p)) return 0;
    for (unsigned lane=0; lane<HD_LANES; ++lane) {
        unsigned meta=*p++, state=meta>=168 ? 2u : meta>=84 ? 1u : 0u;
        HdRoots *r=bank ? &bank->roots[lane] : 0;
        if (r) {
            r->state=(uint8_t)state;
            r->scale=(uint8_t)(meta-state*84u);
            r->context=HD_NONE;
        }
        for (unsigned step=0; step<HD_STEPS; step+=4,p+=5) {
            publish(r,qualities,step,(unsigned)p[0]<<2 | p[1]>>6);
            publish(r,qualities,step+1,((unsigned)p[1]&63u)<<4 | p[2]>>4);
            publish(r,qualities,step+2,((unsigned)p[2]&15u)<<6 | p[3]>>2);
            publish(r,qualities,step+3,((unsigned)p[3]&3u)<<8 | p[4]);
        }
        if (qualities) qualities+=HD_STEPS;
    }
    return 1;
}
