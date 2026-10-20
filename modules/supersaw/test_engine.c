/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "adapter.c"

/* Scalar oracle for the optimized grouping of equal-weight oscillators.
 * Intentionally multiply each lane independently, as the imported engine did. */
static void reference(struct ss_voice *v, const struct ss_params *p,
                      int16_t *out, unsigned count) {
    struct ss_params core = *p;
    if (core.increment < 512) core.increment = 512;
    if (core.increment > 0x3e800000u) core.increment = 0x3e800000u;
    core.increment *= 2;
    while (count--) {
        if (v->pending) {
            *out++ = v->last;
            v->pending = 0;
            continue;
        }
        ss_prepare(v, &core);
        int32_t sum = 0;
        for (unsigned lane = 0; lane < 7; ++lane) {
            sum += lookup(ss_saws[v->bank], v->phase[lane]) *
                   (lane == 3 ? v->centre_weight : v->side_weight);
            v->phase[lane] += v->increments[lane];
        }
        sum += lookup(ss_sine, v->sub_phase) * v->sub_gain;
        v->sub_phase += v->base / 2;
        int32_t value = sum >> 15;
        if (p->drive & 127) {
            int32_t x = (value * v->drive_gain) >> 8;
            if (x > 32767) x = 32767;
            if (x < -32767) x = -32767;
            value = x - (((((x*x) >> 15)*x >> 15)*10923) >> 15);
        }
        *out++ = (int16_t)(((int32_t)v->last + value) >> 1);
        v->last = (int16_t)value;
        v->pending = 1;
    }
}

int main(int argc, char **argv) {
    assert(ss_marker("../AUDIO/FMSYNTH-SUPERSAW.wav"));
    assert(ss_marker("FMSYNTH-SUPERSAW-pad.wav"));
    assert(!ss_marker("FMSYNTH-SUPERSAWish.wav"));
    assert(!ss_marker("FMSYNTH-SOPHIE.wav"));
    assert(!ss_marker("FMSYNTH.wav"));
    assert(!ss_marker(NULL));
    char path[256]; memset(path, 'a', sizeof(path)); assert(!ss_marker(path));
    struct ss_voice a, b, c;
    memset(&a, 0xa5, sizeof(a)); ss_init(&a); ss_init(&b); ss_init(&c);
    assert(!memcmp(&a, &b, sizeof(a)));
    struct ss_params p = {21426141, 100, 110, 64, 80};
    int16_t whole[4096], split[4096], other[4096];
    ss_render(&a, &p, whole, 4096);
    for (unsigned n = 0; n < 4096;) {
        unsigned count = n % 29 + 1;
        if (count > 4096-n) count = 4096-n;
        ss_render(&b, &p, split+n, count); n += count;
    }
    assert(!memcmp(whole, split, sizeof(whole)));
    ss_render(&c, &p, other, 4096);
    assert(!memcmp(whole, other, sizeof(whole)));
    /* Every musical control changes the result at a non-degenerate patch. */
    for (unsigned knob = 0; knob < 4; ++knob) {
        struct ss_params q = p;
        if (knob == 0) q.detune = 0;
        if (knob == 1) q.mix = 0;
        if (knob == 2) q.sub = 0;
        if (knob == 3) q.drive = 0;
        ss_init(&a); ss_render(&a, &q, other, 4096);
        assert(memcmp(whole, other, sizeof(whole)));
    }
    /* Extremes and changing controls under the address/UB sanitizers. */
    for (unsigned i = 0; i < 128; ++i) {
        struct ss_params q = {i % 2 ? 0xffffffffu : i * 16000000u,
                              i, 127-i, i, 127};
        ss_render(&a, &q, other, 4096);
    }
    /* Cached and freshly derived controls agree across held notes, knob
     * changes and odd call splits. The latter forces every recomputation. */
    ss_init(&a); ss_init(&b);
    p = (struct ss_params){21426141,100,110,64,80};
    for (unsigned i = 0; i < 300; ++i) {
        if (i % 5 == 0) p.increment += 123456;
        if (i % 5 == 1) p.detune = (uint8_t)i;
        if (i % 5 == 2) p.mix = (uint8_t)(i*3);
        if (i % 5 == 3) p.sub = (uint8_t)(i*7);
        if (i % 5 == 4) p.drive = (uint8_t)(i*11);
        for (unsigned repeat = 0; repeat < 3; ++repeat) {
            unsigned n = (i+repeat) % 31 + 1;
            b.base = 0;
            ss_render(&a,&p,whole,n); ss_render(&b,&p,split,n);
            assert(!memcmp(whole,split,n*sizeof(*whole)));
        }
    }
    uint32_t state[32] = {0}; uint16_t fp[6] = {0x4000,0,0,0x4000,0,0};
    state[3] = 21426141; state[6] = 32768;
    *(uint16_t *)((uint8_t *)state+38) = 32768;
    int32_t out[64]; for (unsigned i=0;i<64;++i) out[i] = 123;
    assert(!ss_fill(0,(uint8_t *)state,fp,out,16));
    for (unsigned i=0;i<64;++i) assert(out[i] == 123);
    ss_init(&ss_voices[0]); ss_init(&ss_voices[1]); ss_active[0] = ss_active[1] = 1;
    int32_t out2[64];
    assert(ss_fill(0,(uint8_t *)state,fp,out,16));
    assert(ss_fill(1,(uint8_t *)state,fp,out2,16));
    assert(!memcmp(out,out2,32*sizeof(*out)));
    uint32_t held_phase = ss_voices[0].phase[3];
    assert(held_phase);
    ss_activate(0,1,32768); assert(ss_voices[0].phase[3] == held_phase);
    ss_activate(0,1,0); assert(ss_voices[0].phase[3] == 0);
    ((uint8_t *)state)[80] = 1;
    assert(ss_fill(0,(uint8_t *)state,fp,out,16));
    for (unsigned i=0;i<32;++i) assert(out[i] == 0);
    assert(ss_unsupported[0] == 1 && ss_samples[0] == 16 && !ss_active[2]);
    ss_init(&a); ss_init(&b);
    uint32_t random = 1234;
    for (unsigned i = 0; i < 10000; ++i) {
        random = random * 1664525u + 1013904223u;
        struct ss_params q = {random, random>>8, random>>16, random>>24, random};
        unsigned n = i % 129;
        ss_render(&a, &q, whole, n);
        reference(&b, &q, split, n);
        assert(!memcmp(whole, split, n*sizeof(*whole)));
        assert(!memcmp(&a, &b, sizeof(a)));
    }
    if (argc == 2) {
        FILE *f = fopen(argv[1], "wb"); assert(f);
        p = (struct ss_params){21426141,0,0,0,0};
        ss_init(&a); ss_render(&a,&p,whole,4096);
        assert(fwrite(whole,sizeof(*whole),4096,f)==4096); fclose(f);
    }
    puts("[ok] Supersaw split blocks, independent voices, controls, extremes, markers and mono boundary");
    return 0;
}
