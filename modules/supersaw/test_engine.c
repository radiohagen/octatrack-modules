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

/* Independent wide division oracle, including arbitrary four-point
 * interpolation history beyond signed 16-bit and native modulo32 format. */
static int64_t output_floor(int64_t value,int64_t divisor) {
    int64_t result=value/divisor;
    return result-(value<0 && value%divisor!=0);
}
static void check_output_scale(void) {
    const int32_t gains[]={0,1,127,16383,16384,32767,32768};
    for(int32_t sample=-40960;sample<=40959;++sample)
    for(unsigned i=0;i<sizeof(gains)/sizeof(gains[0]);++i) {
        int64_t floor=output_floor((int64_t)sample*gains[i],32768);
        assert(ss_output_scale(sample,gains[i],0)==floor);
        assert((uint32_t)ss_output_scale(sample,gains[i],1)==(uint32_t)(floor*65536));
    }
    /* Dry history can be extreme at internal caller boundaries. Preserve
     * native wrapping as well as PCM output for every endpoint gain ramp. */
    const unsigned levels[]={0,1,32767,32768};
    for(unsigned bits=0;bits<32;++bits)
    for(unsigned from=0;from<4;++from)
    for(unsigned to=0;to<4;++to)
    for(unsigned stereo=0;stereo<2;++stereo)
    for(unsigned filtered=0;filtered<2;++filtered) {
        struct ss_voice actual={0},expected={0};
        actual.last=bits&1?32767:-32768;
        actual.previous=bits&2?32767:-32768;
        actual.older=bits&4?32767:-32768;expected=actual;
        int16_t source[8];int32_t out[32]={0},oracle[32]={0};
        for(unsigned i=0;i<8;++i)source[i]=((bits>>3)^(bits&16?i:0))&1?32767:-32768;
        unsigned previous=levels[from],target=levels[to];
        int64_t gain=(int64_t)previous*16,step=(int64_t)target-previous;
        int32_t p1=expected.last,p2=expected.previous,p3=expected.older;
        for(unsigned i=0;i<8;++i) {
            int64_t interp=output_floor(9*((int64_t)p1+p2)-p3-source[i],16);
            if(filtered) { if(interp>32767)interp=32767;if(interp< -32768)interp= -32768; }
            gain+=step;int64_t first=output_floor(interp*(gain/16),32768);
            gain+=step;int64_t second=output_floor((int64_t)p1*(gain/16),32768);
            if(stereo) {
                oracle[4*i]=oracle[4*i+1]=(int32_t)(uint32_t)(first*65536);
                oracle[4*i+2]=oracle[4*i+3]=(int32_t)(uint32_t)(second*65536);
            } else { oracle[2*i]=(int32_t)first;oracle[2*i+1]=(int32_t)second; }
            p3=p2;p2=p1;p1=source[i];
        }
        expected.last=(int16_t)p1;expected.previous=(int16_t)p2;expected.older=(int16_t)p3;
        ss_output16(&actual,source,out,previous,target,filtered,stereo,
                    previous==target,stereo && previous==target && target==32768);
        assert(!memcmp(out,oracle,sizeof out));assert(!memcmp(&actual,&expected,sizeof actual));
    }
    puts("[ok] native output scaling: full interpolation range, 7 gains, exact PCM/stereo floor and extreme histories");
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

static void check_adapter_lifecycle(void) {
    /* A different synth must not pay to clear Supersaw history. A later
     * Supersaw selection still clears phases/filters and every poly voice. */
    for(unsigned was_active=0;was_active<2;++was_active)
    for(unsigned gain=0;gain<=32768;gain+=32768) {
        const unsigned track=6;
        memset(&ss_voices[track],0xa5,sizeof ss_voices[track]);
        memset(ss_poly_voices[track],0x5a,sizeof ss_poly_voices[track]);
        memset(ss_filters[track],0x3c,sizeof ss_filters[track]);
        struct ss_voice mono=ss_voices[track],poly[4];
        struct ss_filter filters[5],empty={0};
        memcpy(poly,ss_poly_voices[track],sizeof poly);
        memcpy(filters,ss_filters[track],sizeof filters);
        ss_active[track]=(uint8_t)was_active;
        ss_activate(track,0,(uint16_t)gain);
        assert(!ss_active[track]);
        assert(!memcmp(&mono,&ss_voices[track],sizeof mono));
        assert(!memcmp(poly,ss_poly_voices[track],sizeof poly));
        assert(!memcmp(filters,ss_filters[track],sizeof filters));
        ss_activate(track,1,(uint16_t)gain);
        assert(ss_active[track]==1);
        ss_restart(&mono);
        assert(!memcmp(&mono,&ss_voices[track],sizeof mono));
        for(unsigned v=0;v<4;++v) {
            ss_init(&poly[v]);
            assert(!memcmp(&poly[v],&ss_poly_voices[track][v],sizeof poly[v]));
        }
        for(unsigned v=0;v<5;++v)
            assert(!memcmp(&empty,&ss_filters[track][v],sizeof empty));
    }
    /* Exercise every source/destination, odd resampler history and filter
     * envelope. The only changed filter field is its native voice stamp. */
    for(unsigned track=0;track<8;++track)for(unsigned voice=0;voice<4;++voice) {
        struct ss_params p={21426141u+track*123456u,96,110,40,30};
        struct ss_filter_params fp={64,64,80,64,1};
        int16_t audio[3];
        ss_init(&ss_voices[track]);ss_filter_reset(&ss_filters[track][4]);
        ss_render_filtered(&ss_voices[track],&p,audio,3,&ss_filters[track][4],&fp,5);
        assert(ss_voices[track].pending);
        struct ss_voice expected[8][4];struct ss_filter filters[8][5];
        memcpy(expected,ss_poly_voices,sizeof expected);
        memcpy(filters,ss_filters,sizeof filters);
        ss_active[track]=0;ss_carry(track,voice,91);
        assert(!memcmp(expected,ss_poly_voices,sizeof expected));
        assert(!memcmp(filters,ss_filters,sizeof filters));
        ss_active[track]=1;
        expected[track][voice]=ss_voices[track];
        filters[track][voice]=ss_filters[track][4];
        filters[track][voice].stamp=91;
        ss_carry(track,voice,91);
        assert(!memcmp(expected,ss_poly_voices,sizeof expected));
        assert(!memcmp(filters,ss_filters,sizeof filters));
        ss_carry(8,voice,92);ss_carry(track,4,92);
        assert(!memcmp(expected,ss_poly_voices,sizeof expected));
        assert(!memcmp(filters,ss_filters,sizeof filters));
    }
    puts("[ok] unrelated synth selection leaves dormant state untouched; reactivation and all carry targets preserve lifecycle");
}

static void check_single_poly(void) {
    /* Staged rendering plus the old wide gain/mix arithmetic is the oracle.
     * Native state, not the selected polyphony capacity, chooses this path. */
    const uint32_t gains[][2]={{0,0},{0,32767},{32767,0},{32767,32767},
        {12345,23456},{23456,12345},{1,1},{65535,0},{0,UINT32_MAX},
        {65535,UINT32_MAX}};
    const unsigned track=5;
    uint32_t random=1234567;
    for(unsigned slot=0;slot<4;++slot) {
        for(unsigned v=0;v<4;++v)ss_init(&ss_poly_voices[track][v]);
        for(unsigned v=0;v<5;++v)ss_filter_reset(&ss_filters[track][v]);
        ss_active[track]=1;
        for(unsigned block=0;block<1000;++block) {
            random=random*1664525u+1013904223u;
            struct ss_params p={random,(uint8_t)(random>>8)&127,
                (uint8_t)(random>>16)&127,(uint8_t)(random>>24)&127,(uint8_t)random&127};
            struct ss_filter_params f={32+(block%96),block%128,
                (block*7)%128,(block*11)%128,(block/5)%4};
            if(block%13==0)f=(struct ss_filter_params){127,0,0,64,1};
            ss_setup[track][1]=f.resonance;ss_setup[track][2]=f.amount;
            ss_setup[track][3]=f.decay;ss_setup[track][4]=f.type;
            uint16_t fp[6]={0x4000,(uint16_t)p.detune<<8,(uint16_t)p.morph<<8,
                (uint16_t)f.cutoff<<8,(uint16_t)p.sub<<8,(uint16_t)p.drive<<8};
            uint32_t pool[4][16],state[32]={0};
            memset(pool,0xa5,sizeof pool);
            for(unsigned v=0;v<4;++v)((uint8_t *)pool[v])[36]=v==slot?1+block%3:0;
            uint32_t previous=gains[block%10][0],target=gains[block%10][1];
            uint8_t *native=(uint8_t *)pool[slot];
            pool[slot][3]=p.increment;pool[slot][6]=target;pool[slot][12]=block/17;
            *(uint16_t *)(native+60)=(uint16_t)previous;
            ((uint8_t *)state)[80]=1;*(uint16_t *)((uint8_t *)state+38)=1234;
            if(block%7==0) { /* A carried odd sample requires the existing fallback. */
                int16_t warm[3];ss_render(&ss_poly_voices[track][slot],&p,warm,3);
            }
            struct ss_voice voices[4];struct ss_filter filters[5];
            memcpy(voices,ss_poly_voices[track],sizeof voices);
            memcpy(filters,ss_filters[track],sizeof filters);
            uint32_t expected_pool[4][16];memcpy(expected_pool,pool,sizeof pool);
            uint32_t samples=ss_samples[track],filtered=ss_filter_samples[track],counts[4];
            memcpy(counts,ss_poly_samples[track],sizeof counts);counts[slot]+=16;
            int32_t expected[34]={0},actual[34];expected[32]=expected[33]=123456;
            for(unsigned i=0;i<34;++i)actual[i]=123456;
            if(!previous) { ss_restart(&voices[slot]);ss_filter_reset(&filters[slot]); }
            if(previous || target) {
                if(previous>32767)previous=32767;
                if(target>32767)target=32767;
                if(f.type==1 && f.cutoff==127 && !f.resonance && !f.amount)f.type=0;
                int16_t source[16];
                if(f.type || filters[slot].wet) {
                    ss_render_filtered(&voices[slot],&p,source,16,&filters[slot],&f,block/17);
                    filtered+=16;
                } else ss_render(&voices[slot],&p,source,16);
                int64_t gain=(int64_t)previous*65536;
                int64_t step=((int64_t)target-previous)*65536/16;
                for(unsigned i=0;i<16;++i) {
                    gain+=step;
                    int32_t sample=(int32_t)((source[i]*(gain>>16))>>15);
                    expected[2*i]=expected[2*i+1]=sample*65536;
                }
                *(uint16_t *)((uint8_t *)expected_pool[slot]+60)=(uint16_t)target;
            }
            assert(ss_track_fill(track,(uint8_t *)state,fp,actual,16,(uint8_t *)pool));
            assert(!memcmp(expected,actual,sizeof actual));
            assert(!memcmp(expected_pool,pool,sizeof pool));
            assert(!memcmp(voices,ss_poly_voices[track],sizeof voices));
            assert(!memcmp(filters,ss_filters[track],sizeof filters));
            assert(!memcmp(counts,ss_poly_samples[track],sizeof counts));
            assert(ss_samples[track]==samples+16 && ss_filter_samples[track]==filtered);
            assert(!*(uint16_t *)((uint8_t *)state+38));
        }
    }
    puts("[ok] single active poly voice matches staged mixing, all gains/slots/filter modes, sparse state and odd carries");
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

static void check_retired_poly(void) {
    /* No native records are active, even though old gains and private
     * histories remain. Only the output, track count and mono gain change. */
    const unsigned track=7;
    uint16_t fp[6]={0x4000,96<<8,110<<8,64<<8,40<<8,30<<8};
    ss_active[track]=1;
    ss_init(&ss_voices[track]);ss_voices[track].pending=1;
    for(unsigned v=0;v<4;++v) {
        ss_init(&ss_poly_voices[track][v]);
        ss_poly_voices[track][v].phase[0]=1234567u*(v+1);
        ss_poly_voices[track][v].pending=v&1;
    }
    for(unsigned v=0;v<5;++v) {
        ss_filter_reset(&ss_filters[track][v]);
        ss_filters[track][v].wet=128;ss_filters[track][v].stamp=100+v;
    }
    struct ss_voice mono[8],voices[8][4];struct ss_filter filters[8][5];
    memcpy(mono,ss_voices,sizeof mono);memcpy(voices,ss_poly_voices,sizeof voices);
    memcpy(filters,ss_filters,sizeof filters);
    for(unsigned n=0;n<=32;++n) {
        uint32_t state[32],expected_state[32],pool[4][16],expected_pool[4][16];
        memset(state,0xa5,sizeof state);memset(pool,0x5a,sizeof pool);
        ((uint8_t *)state)[80]=1;
        for(unsigned v=0;v<4;++v)((uint8_t *)pool[v])[36]=0;
        memcpy(expected_state,state,sizeof state);memcpy(expected_pool,pool,sizeof pool);
        if(n)*(uint16_t *)((uint8_t *)expected_state+38)=0;
        uint32_t samples[8],poly_samples[8][4],filtered[8],unsupported[8];
        memcpy(samples,ss_samples,sizeof samples);samples[track]+=n;
        memcpy(poly_samples,ss_poly_samples,sizeof poly_samples);
        memcpy(filtered,ss_filter_samples,sizeof filtered);
        memcpy(unsupported,ss_unsupported,sizeof unsupported);
        int32_t guarded[66];
        for(unsigned i=0;i<66;++i)guarded[i]=123456;
        assert(ss_track_fill(track,(uint8_t *)state,fp,guarded+1,n,(uint8_t *)pool));
        assert(guarded[0]==123456);
        for(unsigned i=1;i<=2*n;++i)assert(!guarded[i]);
        for(unsigned i=1+2*n;i<66;++i)assert(guarded[i]==123456);
        assert(!memcmp(state,expected_state,sizeof state));
        assert(!memcmp(pool,expected_pool,sizeof pool));
        assert(!memcmp(samples,ss_samples,sizeof samples));
        assert(!memcmp(poly_samples,ss_poly_samples,sizeof poly_samples));
        assert(!memcmp(filtered,ss_filter_samples,sizeof filtered));
        assert(!memcmp(unsupported,ss_unsupported,sizeof unsupported));
        assert(!memcmp(mono,ss_voices,sizeof mono));
        assert(!memcmp(voices,ss_poly_voices,sizeof voices));
        assert(!memcmp(filters,ss_filters,sizeof filters));
    }
    puts("[ok] retired poly: all lengths 0-32, output guards, native state and unchanged voice/filter bookkeeping");
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

/* Independent coefficient arithmetic, without production cache guards,
 * symmetric-offset reuse or the leading-zero bank shortcut. */
static void reference_prepare(struct ss_voice *v,const struct ss_params *p) {
    uint32_t base=p->increment,maximum=0;
    if(base<1024)base=1024;
    if(base>0x7d000000u)base=0x7d000000u;
    uint8_t controls[4]={p->detune&127,p->morph&127,p->sub&127,p->drive&127};
    memcpy(&v->controls,controls,sizeof controls);v->base=base;
    for(unsigned i=0;i<2;++i) {
        int32_t delta=(int32_t)ss_ratios[controls[0]][i]-1048576;
        int32_t offset=((int32_t)(base>>16)*delta+
            (int32_t)(base&65535)*delta/65536)/16;
        v->increments[i]=(uint32_t)((int32_t)base+offset);
        if(v->increments[i]>maximum)maximum=v->increments[i];
    }
    unsigned bank=0;
    while(bank<7 && maximum<=(0x7fffffffu>>(bank+1)))++bank;
    uint64_t lower=(uint64_t)1<<(30-bank);
    unsigned fade=bank && maximum>lower ?
        (unsigned)((((uint64_t)maximum-lower)*16+lower/2)/lower) : 0;
    v->bank=bank*16-fade;
    v->sub_gain=(int32_t)controls[2]*64;
    v->saw_weight=(32768-v->sub_gain)/2;
    v->morph_weight=(v->saw_weight*ss_morph_polarity[controls[1]])>>15;
    v->drive_gain=256+(int32_t)controls[3]*6;
}

static void check_prepare_case(struct ss_voice *actual,struct ss_voice *expected,
                               const struct ss_params *p) {
    reference_prepare(expected,p);ss_prepare(actual,p);
    assert(!memcmp(actual,expected,sizeof *actual));
}

static void check_prepare(void) {
    unsigned cases=0;
    const uint32_t edges[]={0,1023,1024,1025,0x7cffffffu,0x7d000000u,
        0x7d000001u,UINT32_MAX};
    for(unsigned detune=0;detune<128;++detune) {
        assert(ss_ratios[detune][0]+ss_ratios[detune][1]==2*1048576);
        for(unsigned boundary=0;boundary<40;++boundary)
        for(int delta=-4;delta<=4;++delta) {
            /* The highest oscillator crosses each power-of-two bank
             * threshold near base = threshold / positive detune ratio. */
            int64_t candidate=boundary<32 ?
                (int64_t)(((uint64_t)1<<boundary)*1048576/ss_ratios[detune][1])+delta :
                edges[boundary-32];
            uint32_t base=candidate<0?0:candidate>UINT32_MAX?UINT32_MAX:(uint32_t)candidate;
            struct ss_params p={base,detune,37,61,89};
            struct ss_voice actual,expected;ss_init(&actual);ss_init(&expected);
            check_prepare_case(&actual,&expected,&p);++cases; /* Cold. */
            check_prepare_case(&actual,&expected,&p);++cases; /* Held cache hit. */
            p.increment^=0x12345;
            check_prepare_case(&actual,&expected,&p);++cases; /* Pitch only. */
            p.morph^=127;p.sub^=127;p.drive^=127;
            check_prepare_case(&actual,&expected,&p);++cases; /* Timbre only. */
            p.detune^=128;p.morph^=128;p.sub^=128;p.drive^=128;
            check_prepare_case(&actual,&expected,&p);++cases; /* High bits ignored. */
            ss_restart(&actual);ss_restart(&expected);
            p.detune^=127;
            check_prepare_case(&actual,&expected,&p);++cases; /* Warm cache, cold phase. */
        }
    }
    printf("[ok] independent two-ratio/threshold coefficient oracle: %u cold, cached and split-control cases\n",cases);
}

static void check_bank_boundaries(void) {
    assert(sizeof ss_saws/sizeof ss_saws[0]==113);
    struct ss_voice v,expected;ss_init(&v);ss_init(&expected);
    /* Every former octave jump now meets at one shared table, including
     * the two-harmonic to sine transition. Walk both sides at one phase LSB. */
    for(unsigned bank=1;bank<8;++bank) {
        uint32_t boundary=0x80000000u>>bank;
        for(int d=-4;d<=4;++d) {
            struct ss_params p={boundary+d,0,0,0,0};
            check_prepare_case(&v,&expected,&p);
            assert(v.bank==(bank-1)*16);
        }
        for(unsigned step=0;step<16;++step) {
            /* Independent rounded-blend thresholds: test below, at, and
             * above each midpoint, with both extreme detune settings. */
            uint64_t lower=(uint64_t)1<<(30-bank);
            uint64_t threshold=lower+lower*(2*step+1)/32;
            for(unsigned detune=0;detune<128;detune+=127)
            for(int d=-4;d<=4;++d) {
                uint32_t base=(uint32_t)(threshold*1048576/ss_ratios[detune][1])+d;
                struct ss_params p={base,detune,0,0,0};
                check_prepare_case(&v,&expected,&p);
                assert(v.bank<=112);
                unsigned power=(v.bank+15)/16;
                assert((uint64_t)v.increments[1]*((uint64_t)1<<power)<0x80000000u);
            }
        }
    }
    puts("[ok] all seven octave bank joins are identical; blend thresholds and detune retain harmonic bounds");
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
    check_restart();check_prepare();check_bank_boundaries();check_filter();check_half_filter();
    check_gain();check_output_scale();
    check_mix16();check_poly();check_adapter_lifecycle();check_single_poly();check_retired_poly();
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
