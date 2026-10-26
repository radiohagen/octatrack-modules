/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define SS_HOST_TEST
#include "adapter.c"
#include "filter_reference.h"

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
            x=((x+32772)>>3)*8-32768;
            if(x>32767)x=32767;if(x< -32767)x= -32767;
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
                if(n && !levels[k][0] && !levels[k][1])ss_init(&oracle);
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

static void check_mix16(void) {
    /* The established staged renderer is the oracle: exercise exact gain
     * rounding, all filter modes/fades, extremes, retriggers and controls. */
    struct ss_voice actual,reference_voice;
    struct ss_filter filter={0},reference_filter={0};
    ss_init(&actual);ss_init(&reference_voice);
    uint32_t random=1234;
    for(unsigned block=0;block<20000;++block) {
        random=random*1664525u+1013904223u;
        struct ss_params p={random,(uint8_t)(random>>8),(uint8_t)(random>>16),
                            (uint8_t)(random>>24),(uint8_t)random};
        struct ss_filter_params fp={random%128,(random>>8)%128,
                                   (random>>16)%128,(random>>24)%128,block%4};
        unsigned filtered=block%7!=0;
        unsigned previous=(random>>5)%32768,target=(random>>17)%32768;
        if(block%3==0)target=previous;
        if(block%5==0)previous=0;
        if(block%11==0)target=0;
        if(block%13==0) { ss_restart(&actual);ss_restart(&reference_voice);
            ss_filter_reset(&filter);ss_filter_reset(&reference_filter); }
        struct ss_voice stereo_voice=actual;
        struct ss_filter stereo_filter=filter;
        int16_t audio[16];int32_t mix[18],expected[18],stereo[34];
        for(unsigned i=0;i<34;++i)stereo[i]=123456;
        for(unsigned i=0;i<18;++i)mix[i]=expected[i]=(int32_t)(i*701)-9000;
        if(filtered)ss_render_filtered(&reference_voice,&p,audio,16,&reference_filter,&fp,block/9);
        else ss_render(&reference_voice,&p,audio,16);
        int64_t gain=(int64_t)previous*65536;
        int64_t step=((int64_t)target-previous)*65536/16;
        for(unsigned i=0;i<16;++i) { gain+=step;expected[i]+=(int32_t)((audio[i]*(gain>>16))>>15); }
        ss_mix16(&actual,&p,mix,previous,target,filtered?&filter:0,&fp,block/9);
        assert(!memcmp(mix,expected,sizeof mix));
        ss_stereo16(&stereo_voice,&p,stereo,previous,target,filtered?&stereo_filter:0,&fp,block/9);
        for(unsigned i=0;i<16;++i) {
            int32_t sample=expected[i]-((int32_t)(i*701)-9000);
            assert(stereo[2*i]==sample*65536 && stereo[2*i+1]==stereo[2*i]);
        }
        assert(stereo[32]==123456 && stereo[33]==123456);
        assert(!memcmp(&stereo_voice,&reference_voice,sizeof actual));
        assert(!memcmp(&stereo_filter,&reference_filter,sizeof filter));
        assert(!memcmp(&actual,&reference_voice,sizeof actual));
        assert(!memcmp(&filter,&reference_filter,sizeof filter));
    }
    puts("[ok] fused native-frame mix matches staged audio and all voice/filter state for 20000 blocks");
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
    ss_filters[3][4].envelope=12345;
    ss_carry(3,2,91);assert(ss_filters[3][2].envelope==12345 && ss_filters[3][2].stamp==91);assert(!memcmp(&ss_voices[3],&ss_poly_voices[3][2],sizeof(struct ss_voice)));
    /* Inactive native voices leave the existing mono render bit-identical. */
    memset(pool,0,sizeof(pool));memset(state,0,sizeof(state));state[3]=21426141;state[6]=32768;
    ss_init(&ss_voices[3]);ss_init(&ss_voices[4]);ss_active[4]=1;
    uint32_t copy[32];memcpy(copy,state,sizeof(state));int32_t mono[64];
    ss_fill(4,(uint8_t *)copy,fp,mono,32);
    ss_track_fill(3,(uint8_t *)state,fp,out,32,(uint8_t *)pool);
    assert(!memcmp(out,mono,sizeof(mono)));
    /* The poly -> mono tail is mixed, and releasing it leaves mono alone. */
    ss_carry(3,0,92);pool[0][3]=21426141;pool[0][6]=0;
    ((uint8_t *)pool)[36]=3;*(uint16_t *)((uint8_t *)pool+60)=16384;
    memcpy(copy,state,sizeof(state));ss_voices[4]=ss_voices[3];
    ss_fill(4,(uint8_t *)copy,fp,mono,16);
    ss_track_fill(3,(uint8_t *)state,fp,out,16,(uint8_t *)pool);
    assert(memcmp(out,mono,32*sizeof(*out)));assert(!*(uint16_t *)((uint8_t *)pool+60));
}

static void check_filter(void) {
    /* Exhaustive generated-table equivalence to the original runtime division. */
    for(unsigned r=0;r<128;++r)for(unsigned c=0;c<128;++c) {
        int32_t g=ss_filter_g[c],k=ss_filter_damping[r];
        int32_t den=16384+ss_reference_mul(k,g)+ss_reference_mul(g,g);
        assert(ss_filter_a1[r][c]==268435456/den);
    }
    for(int delta=-100000;delta<=100000;delta+=13)
        for(unsigned n=1;n<=32;++n)assert(ss_filter_step(delta,n)==delta/(int)n);
    struct ss_filter a={0},b={0};
    struct ss_filter_params p={64,64,80,64,0};
    int16_t audio[32],copy[32];
    for(unsigned i=0;i<32;++i)audio[i]=(int16_t)(i*1713-23000);
    memcpy(copy,audio,sizeof audio);ss_filter_run(&a,&p,1,audio,32);
    assert(!memcmp(copy,audio,sizeof audio));assert(!a.wet);
    p.type=1;
    for(unsigned j=0;j<100;++j){memcpy(audio,copy,sizeof audio);ss_filter_run(&a,&p,1,audio,32);}
    b=a;uint32_t before=a.envelope;
    memcpy(audio,copy,sizeof audio);ss_filter_run(&a,&p,2,audio,32);
    assert(a.envelope>before && b.envelope==before);
    p.type=0;
    for(unsigned j=0;j<5;++j){memcpy(audio,copy,sizeof audio);ss_filter_run(&a,&p,2,audio,32);}
    assert(!memcmp(copy,audio,sizeof audio));assert(!a.wet);
    struct ss_filter original=a;
    unsigned random=123456;
    for(unsigned j=0;j<100000;++j){
        random=random*1664525u+1013904223u;
        p=(struct ss_filter_params){random,random>>8,random>>16,random>>24,(random>>6)&3};
        for(unsigned k=0;k<32;++k)audio[k]=(int16_t)(random+k*3331);
        memcpy(copy,audio,sizeof audio);
        ss_filter_reference(&original,&p,j/13,copy,j%33);
        ss_filter_run(&a,&p,j/13,audio,j%33);
        assert(!memcmp(copy,audio,sizeof audio));
        assert(!memcmp(&original,&a,sizeof a));
        assert(a.s0>=-8388607 && a.s0<=8388607 && a.s1>=-8388607 && a.s1<=8388607);
        assert(a.envelope<=(1u<<24));
    }
    /* Exercise each specialized steady loop, including after the envelope
     * reaches zero and after live switches/bypass fades, against S7 math. */
    for(unsigned typ=1;typ<=3;++typ)for(unsigned cut=0;cut<128;cut+=21)
    for(unsigned res=0;res<128;res+=63) {
        ss_filter_reset(&a);ss_filter_reset(&original);
        p=(struct ss_filter_params){cut,res,0,0,typ};
        for(unsigned block=0;block<128;++block) {
            if(block==80)p.type=0;
            if(block==96)p.type=typ;
            for(unsigned i=0;i<32;++i)audio[i]=(int16_t)(block*3191u+i*6713u);
            memcpy(copy,audio,sizeof audio);
            ss_filter_reference(&original,&p,1,copy,32);
            ss_filter_run(&a,&p,1,audio,32);
            assert(!memcmp(copy,audio,sizeof audio));
            assert(!memcmp(&original,&a,sizeof a));
        }
    }
    puts("[ok] SEM bit-exact S7 reference: steady modes, bypass, envelopes and 100000 extreme modulation blocks");
}

/* Independent 64-bit scalar filter oracle at the production source rate.
 * Extreme random blocks cover interpolation coefficients, all modes/fades,
 * every split size, and ENV/DEC edits on already-running notes. */
static void check_half_filter(void) {
    struct ss_filter a={0},b={0};
    uint32_t random=93573;
    for(unsigned r=0;r<128;++r)for(unsigned c=0;c<128;++c) {
        int64_t g=ss_filter_half_g[c],k=ss_filter_damping[r];
        assert(ss_filter_half_a1[r][c]==268435456/(16384+((k*g)>>14)+((g*g)>>14)));
    }
    for(unsigned j=0;j<100000;++j) {
        random=random*1664525u+1013904223u;
        struct ss_filter_params p={random,random>>8,random>>16,random>>24,(random>>6)&3};
        int16_t actual[16],expected[16];
        for(unsigned i=0;i<16;++i)actual[i]=(int16_t)(random+i*3331);
        memcpy(expected,actual,sizeof actual);
        ss_filter_half(&a,&p,j/13,actual,j%17);
        ss_filter_reference_rate(&b,&p,j/13,expected,j%17,2);
        assert(!memcmp(actual,expected,sizeof actual));
        assert(!memcmp(&a,&b,sizeof a));
    }
    /* Filtered render can saturate at high resonance but cannot wrap the
     * upsampler peak. Cross-check every sample against explicit stages. */
    for(unsigned type=0;type<=3;++type)for(unsigned cut=0;cut<128;cut+=17) {
        struct ss_voice v,oracle;ss_init(&v);ss_init(&oracle);
        struct ss_filter filter={0},scalar={0};
        struct ss_params p={21426141,127,0,127,127};
        struct ss_filter_params fp={cut,127,127,0,type};
        int16_t history[3]={0};
        for(unsigned block=0;block<100;++block) {
            int16_t actual[32],source[16],expected[32];
            struct ss_params core=p;core.increment*=2;ss_prepare(&oracle,&core);
            for(unsigned i=0;i<16;++i) {
                int32_t x=(lookup(ss_saws[oracle.bank],oracle.phase[0])*oracle.saw_weight
                          +lookup(ss_saws[oracle.bank],oracle.phase[1])*oracle.morph_weight
                          +lookup(ss_sine,oracle.sub_phase)*oracle.sub_gain)>>15;
                oracle.phase[0]+=oracle.increments[0];oracle.phase[1]+=oracle.increments[1];
                oracle.sub_phase+=oracle.base/2;
                x=(x*oracle.drive_gain)>>8;if(x>32767)x=32767;if(x< -32767)x= -32767;
                x=((x+32772)>>3)*8-32768;
                if(x>32767)x=32767;if(x< -32767)x= -32767;
                source[i]=x-(((((x*x)>>15)*x>>15)*10923)>>15);
            }
            ss_filter_reference_rate(&scalar,&fp,1,source,16,2);
            for(unsigned i=0;i<16;++i) {
                int32_t x=(9*((int32_t)history[0]+history[1])-history[2]-source[i])>>4;
                if(x>32767)x=32767;if(x< -32768)x= -32768;
                expected[2*i]=x;expected[2*i+1]=history[0];
                history[2]=history[1];history[1]=history[0];history[0]=source[i];
            }
            ss_render_filtered(&v,&p,actual,32,&filter,&fp,1);
            assert(!memcmp(actual,expected,sizeof actual));
        }
    }
    /* At fixed controls, arbitrary output splits must preserve the filtered
     * source stream, including odd pending samples and the in-place scratch. */
    for(unsigned type=0;type<=3;++type) {
        struct ss_voice whole_voice,split_voice;ss_init(&whole_voice);
        struct ss_filter whole_filter={0},split_filter;
        struct ss_params p={21426141,96,40,32,64};
        struct ss_filter_params fp={80,96,0,64,type};
        int16_t whole[257],split[257];
        ss_render_filtered(&whole_voice,&p,whole,128,&whole_filter,&fp,1);
        split_voice=whole_voice;split_filter=whole_filter;
        ss_render_filtered(&whole_voice,&p,whole,257,&whole_filter,&fp,1);
        for(unsigned i=0;i<257;) {
            unsigned n=i%31+1;if(n>257-i)n=257-i;
            ss_render_filtered(&split_voice,&p,split+i,n,&split_filter,&fp,1);i+=n;
        }
        assert(!memcmp(whole,split,sizeof whole));
        assert(!memcmp(&whole_voice,&split_voice,sizeof whole_voice));
        assert(whole_filter.s0==split_filter.s0 && whole_filter.s1==split_filter.s1);
    }
    /* A zero-gain poly voice remains silent without consuming render work;
     * its next attack starts from the same reset history as before. */
    uint32_t state[32]={0},pool[4][16]={{0}};int32_t out[64];
    uint16_t controls[6]={0x4000,96<<8,0,64<<8,0,0};
    ((uint8_t *)state)[80]=1;ss_active[6]=1;ss_setup[6][4]=1;
    for(unsigned v=0;v<4;++v) { ((uint8_t *)pool[v])[36]=1;pool[v][3]=21426141*(v+1); }
    ss_track_fill(6,(uint8_t *)state,controls,out,32,(uint8_t *)pool);
    for(unsigned i=0;i<64;++i)assert(!out[i]);
    assert(!ss_filter_samples[6]);
    for(unsigned v=0;v<4;++v)assert(ss_poly_samples[6][v]==32);
    /* Neutral LOW is genuinely transparent, and resumes filtering when
     * CUT closes. After reopening, its filter work must stop after the fade. */
    uint32_t dry_state[32]={0};
    memset(state,0,sizeof(state));memset(ss_setup[5],0,6);memset(ss_setup[4],0,6);
    ss_active[4]=ss_active[5]=1;ss_init(&ss_voices[4]);ss_init(&ss_voices[5]);
    ss_filter_reset(&ss_filters[4][4]);ss_filter_reset(&ss_filters[5][4]);
    ss_setup[5][4]=1;controls[3]=127<<8;
    state[3]=dry_state[3]=21426141;state[6]=dry_state[6]=32768;
    *(uint16_t *)((uint8_t *)state+38)=*(uint16_t *)((uint8_t *)dry_state+38)=32768;
    int32_t dry[64];
    for(unsigned block=0;block<20;++block) {
        ss_fill(4,(uint8_t *)dry_state,controls,dry,32);
        ss_fill(5,(uint8_t *)state,controls,out,32);
        assert(!memcmp(dry,out,sizeof dry));
    }
    assert(!ss_filter_samples[5]);controls[3]=64<<8;
    for(unsigned block=0;block<20;++block)ss_fill(5,(uint8_t *)state,controls,out,32);
    assert(ss_filter_samples[5] && ss_filters[5][4].wet==128);
    controls[3]=127<<8;
    for(unsigned block=0;block<20;++block)ss_fill(5,(uint8_t *)state,controls,out,32);
    uint32_t done=ss_filter_samples[5];assert(!ss_filters[5][4].wet);
    for(unsigned block=0;block<20;++block)ss_fill(5,(uint8_t *)state,controls,out,32);
    assert(ss_filter_samples[5]==done);
    /* ENV=0 still advances elapsed envelope time with O(1) work. */
    struct ss_filter timed={0};struct ss_filter_params no_env={64,64,0,64,1};
    int16_t silent[8]={0};
    ss_filter_half(&timed,&no_env,1,silent,8);uint32_t early=timed.envelope;
    for(unsigned block=0;block<100;++block)ss_filter_half(&timed,&no_env,1,silent,8);
    assert(timed.envelope<early);early=timed.envelope;no_env.amount=127;
    ss_filter_half(&timed,&no_env,1,silent,8);assert(timed.envelope<early);
    ss_filter_half(&timed,&no_env,2,silent,8);assert(timed.envelope>early);
    puts("[ok] half-rate SEM scalar oracle: 100000 extreme blocks, resonant resampling, silent skip, neutral bypass, live ENV");
}

/* Reusing coefficients must be indistinguishable from a full cold reset,
 * even when a new note changes controls, pitch, or the split-call phase. */
static void check_restart(void) {
    struct ss_voice cached,fresh;ss_init(&cached);
    uint32_t seed=719;
    for(unsigned k=0;k<2000;++k) {
        seed=seed*1664525u+1013904223u;
        struct ss_params p={seed,(seed>>4)&127,(seed>>11)&127,
                            (seed>>18)&127,(seed>>25)&127};
        int16_t a[33],b[33];
        ss_render(&cached,&p,a,1+k%32);
        struct ss_voice before=cached;
        ss_restart(&cached);ss_init(&fresh);
        assert(cached.base==before.base && cached.controls==before.controls);
        assert(cached.saw_weight==before.saw_weight);
        if(k&1)p.increment^=0x777777;
        if(k&2)p.sub^=127;
        if(k&4)p.drive^=127;
        ss_render(&cached,&p,a,33);ss_render(&fresh,&p,b,33);
        assert(!memcmp(a,b,sizeof(a)));
        assert(!memcmp(&cached,&fresh,sizeof(cached)));
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
    for(int x=-32767;x<=32767;++x) {
        int exact=x-(((((x*x)>>15)*x>>15)*10923)>>15);
        assert(abs(ss_drive_curve[(x+32772)>>3]-exact)<=5);
    }
    check_restart();check_filter();check_half_filter();
    check_gain();
    check_mix16();check_poly();
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
