/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "adapter.c"

/* Scalar oracle for the chunked oscillator and resampler paths. */
static void reference(struct ss_voice *v, const struct ss_params *p,
                      int16_t *out, unsigned count) {
    struct ss_params core = *p;
    if (core.increment < 512) core.increment = 512;
    if (core.increment > 0x3e800000u) core.increment = 0x3e800000u;
    core.increment *= 2;
    while (count--) {
        if (v->pending) {
            *out++ = v->previous;
            v->pending = 0;
            continue;
        }
        ss_prepare(v, &core);
        int32_t sum = 0;
        for (unsigned lane = 0; lane < 2; ++lane) {
            sum += lookup(ss_saws[v->bank], v->phase[lane]) *
                   (lane == 0 ? v->saw_weight : v->morph_weight);
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
        *out++ = (int16_t)((9*((int32_t)v->last + v->previous) - v->older - value) >> 4);
        v->older = v->previous; v->previous = v->last;
        v->last = (int16_t)value;
        v->pending = 1;
    }
}

/* The old Q15 envelope is an independent, wide-arithmetic oracle. In
 * particular, a 32-sample 0 -> full attack must not overflow its accumulator.
 * Native frames use at most 16; the adapter also accepts a 32-sample buffer. */
static void check_gain(void) {
    const uint16_t levels[][2] = {{0,0},{32768,32768},{12345,12345},
        {0,32768},{32768,0},{12345,23456},{65535,0},{40000,40000}};
    for (unsigned k=0; k<sizeof(levels)/sizeof(levels[0]); ++k) {
        for (unsigned n=0; n<=32; ++n) {
            struct ss_voice oracle;
            ss_init(&oracle); ss_init(&ss_voices[7]);
            ss_active[7]=1; ss_samples[7]=0;
            struct ss_params p={21426141,96,110,40,30};
            uint16_t fp[6]={0x4000,96<<8,110<<8,0x4000,40<<8,30<<8};
            for (unsigned repeat=0; repeat<3; ++repeat) {
                uint32_t state[32]={0};
                state[3]=p.increment; state[6]=levels[k][1];
                *(uint16_t *)((uint8_t *)state+38)=levels[k][0];
                int16_t source[32]; int32_t output[68];
                for (unsigned i=0;i<68;++i) output[i]=123456;
                reference(&oracle,&p,source,n);
                assert(ss_fill(7,(uint8_t *)state,fp,output,n));
                int64_t gain=(int64_t)levels[k][0]*32768;
                int64_t step=((int64_t)levels[k][1]*32768-gain)/16;
                for (unsigned i=0;i<n;++i) {
                    gain+=step;
                    int64_t g=gain>0 ? gain/32768 : 0;
                    if (g>32768) g=32768;
                    int32_t expected=(int32_t)(((source[i]*g)>>15)*65536);
                    assert(output[2*i]==expected && output[2*i+1]==expected);
                }
                for (unsigned i=2*n;i<68;++i) assert(output[i]==123456);
                assert(*(uint16_t *)((uint8_t *)state+38)==
                       (uint16_t)(gain>0 ? gain/32768 : 0));
                assert(!memcmp(&oracle,&ss_voices[7],sizeof(oracle)));
                assert(ss_samples[7]==n*(repeat+1));
            }
        }
    }
}

static void check_poly(void) {
    uint32_t pool[4][16]={{0}}, state[32]={0};
    uint16_t fp[6]={0x4000,96<<8,110<<8,0x4000,40<<8,30<<8};
    struct ss_voice oracle[4];
    int32_t out[66];
    ss_active[3]=1; ss_samples[3]=0;
    ((uint8_t *)state)[80]=1;
    for (unsigned v=0;v<4;++v) {
        ss_init(&oracle[v]); ss_init(&ss_poly_voices[3][v]);
        ss_poly_samples[3][v]=0;
    }
    unsigned total=0;
    for (unsigned round=0;round<100;++round) {
        unsigned n=round%33;
        int32_t expected[32]={0};
        for (unsigned v=0;v<4;++v) {
            uint8_t *native=(uint8_t *)pool[v];
            native[36]=(round%11==v) ? 0 : 1;
            pool[v][3]=21426141u*(v+1); /* Four independently pitched notes. */
            pool[v][6]=(round%7==v) ? 0 : (round%5==v ? 32767 : 16384);
            if (!n || !native[36]) continue;
            unsigned previous=*(uint16_t *)(native+60),target=pool[v][6];
            if (!previous) ss_init(&oracle[v]);
            struct ss_params p={pool[v][3],96,110,40,30};
            int16_t audio[32]; reference(&oracle[v],&p,audio,n);
            int64_t gain=(int64_t)previous*65536;
            int64_t step=((int64_t)target-previous)*65536/n;
            for (unsigned i=0;i<n;++i) {
                gain+=step; expected[i]+=(int32_t)((audio[i]*(gain>>16))>>15);
            }
        }
        for (unsigned i=0;i<66;++i) out[i]=123456;
        assert(ss_track_fill(3,(uint8_t *)state,fp,out,n,(uint8_t *)pool));
        for (unsigned i=0;i<n;++i) {
            int32_t x=expected[i];if(x>32767)x=32767;if(x< -32768)x= -32768;
            assert(out[2*i]==x*65536 && out[2*i+1]==out[2*i]);
        }
        for (unsigned i=2*n;i<66;++i) assert(out[i]==123456);
        for (unsigned v=0;v<4;++v) assert(!memcmp(&oracle[v],&ss_poly_voices[3][v],sizeof(oracle[v])));
        total+=n;assert(ss_samples[3]==total);
    }
    /* Coherent four-note peaks saturate instead of wrapping signed 16.16. */
    memset(pool,0,sizeof(pool));fp[2]=0;fp[4]=0;fp[5]=127<<8;
    for (unsigned v=0;v<4;++v) {
        pool[v][3]=21426141;pool[v][6]=16384;((uint8_t *)pool[v])[36]=1;
        *(uint16_t *)((uint8_t *)pool[v]+60)=16384;ss_init(&ss_poly_voices[3][v]);
    }
    ss_track_fill(3,(uint8_t *)state,fp,out,32,(uint8_t *)pool);
    unsigned saturated=0;
    for(unsigned i=0;i<32;++i) saturated+=(out[2*i]==INT32_MIN || out[2*i]==2147418112);
    assert(saturated);fp[2]=110<<8;fp[4]=40<<8;fp[5]=30<<8;
    /* Native mono -> poly carries every resampler/oscillator bit. */
    ss_init(&ss_voices[3]);struct ss_params p={21426141,96,110,40,30};
    int16_t scratch[3];ss_render(&ss_voices[3],&p,scratch,3);
    ss_carry(3,2);assert(!memcmp(&ss_voices[3],&ss_poly_voices[3][2],sizeof(struct ss_voice)));
    /* Inactive native voices leave the existing mono render bit-identical. */
    memset(pool,0,sizeof(pool));memset(state,0,sizeof(state));state[3]=21426141;state[6]=32768;
    ss_init(&ss_voices[3]);ss_init(&ss_voices[4]);ss_active[4]=1;
    uint32_t copy[32];memcpy(copy,state,sizeof(state));int32_t mono[64];
    ss_fill(4,(uint8_t *)copy,fp,mono,32);
    ss_track_fill(3,(uint8_t *)state,fp,out,32,(uint8_t *)pool);
    assert(!memcmp(out,mono,sizeof(mono)));
    /* The poly -> mono tail is mixed, and releasing it leaves mono alone. */
    ss_carry(3,0);pool[0][3]=21426141;pool[0][6]=0;
    ((uint8_t *)pool)[36]=3;*(uint16_t *)((uint8_t *)pool+60)=16384;
    memcpy(copy,state,sizeof(state));ss_voices[4]=ss_voices[3];
    ss_fill(4,(uint8_t *)copy,fp,mono,16);
    ss_track_fill(3,(uint8_t *)state,fp,out,16,(uint8_t *)pool);
    assert(memcmp(out,mono,32*sizeof(*out)));assert(!*(uint16_t *)((uint8_t *)pool+60));
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
        if (knob == 1) q.morph = 0;
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
        if (i % 5 == 2) p.morph = (uint8_t)(i*3);
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
    uint32_t held_phase = ss_voices[0].phase[0];
    assert(held_phase);
    ss_activate(0,1,32768); assert(ss_voices[0].phase[0] == held_phase);
    ss_activate(0,1,0); assert(ss_voices[0].phase[0] == 0);
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
        for (unsigned j=0;j<n;++j) assert(whole[j]>=-27308 && whole[j]<=27308);
        assert(!memcmp(&a, &b, sizeof(a)));
    }
    /* Fixed pair per note: +/-1.5625% spread, independent sub, no hidden
     * seven-lane state. MORF endpoints are equally weighted sum/difference. */
    assert(sizeof(a.phase)/sizeof(a.phase[0])==2);
    ss_init(&a); p=(struct ss_params){21426141,127,0,0,0};
    ss_render(&a,&p,whole,2);
    assert(a.increments[0]+a.increments[1]==2*a.base);
    assert(abs((int)(a.base-a.increments[0])-(int)(a.base/64))<=1);
    assert(a.saw_weight==a.morph_weight);
    uint32_t phases[2]={a.phase[0],a.phase[1]};
    p.morph=127;ss_render(&a,&p,whole,2);
    assert(a.morph_weight==-a.saw_weight);
    assert(a.phase[0]==phases[0]+a.increments[0]);
    assert(a.phase[1]==phases[1]+a.increments[1]);
    check_gain();
    check_poly();
    if (argc == 2) {
        FILE *f = fopen(argv[1], "wb"); assert(f);
        p = (struct ss_params){21426141,0,0,0,0};
        ss_init(&a); ss_render(&a,&p,whole,4096);
        assert(fwrite(whole,sizeof(*whole),4096,f)==4096);
        p.morph=127; ss_init(&a); ss_render(&a,&p,whole,4096);
        assert(fwrite(whole,sizeof(*whole),4096,f)==4096); fclose(f);
    }
    puts("[ok] Supersaw split blocks, independent voices, controls, extremes, markers and mono/four-note lifecycles");
    return 0;
}
