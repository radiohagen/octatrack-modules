/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "adapter.c"

static uint32_t random_state = 0x051706a5u;
static uint32_t next_random(void) {
    random_state ^= random_state << 13;
    random_state ^= random_state >> 17;
    random_state ^= random_state << 5;
    return random_state;
}

static void test_specialized_engine(void) {
    const uint16_t pitches[]={8,9,15,16,17,32,1024,8192,16383,16384,24575,24576};
    const int8_t sweeps[]={-64,-63,-1,0,1,62,63};
    struct sf_voice specialized;
    struct ds_voice reference;
    int32_t expected[32];
    unsigned calls=0, saw_sleep=0, saw_wake=0;
    memset(&specialized,0,sizeof(specialized));
    memset(&reference,0,sizeof(reference));
    ds_voice_init(&specialized.engine);ds_voice_init(&reference);
    /* sf_fill fixes FUSE/full velocity before any refill. Expose only those
     * existing constants to the compiler, then compare every sample and all
     * engine history to the independently callable, generic upstream code. */
    for(unsigned pitch=0;pitch<sizeof(pitches)/sizeof(*pitches);++pitch)
    for(unsigned sweep=0;sweep<sizeof(sweeps)/sizeof(*sweeps);++sweep)
    for(unsigned mode=0;mode<6;++mode)
    for(unsigned block=0;block<128;++block) {
        specialized.params=(struct ds_params){
            .phase_inc=pitches[pitch],.sweep=sweeps[sweep],
            .model=0,.velocity=127,.fold=0,
            .color=mode==0?0:mode==1?127:next_random()%128,
            .metal=mode==2?0:mode==3?127:next_random()%128,
            .feedback=mode==4?0:mode==5?127:next_random()%128,
        };
        specialized.trigger=block==1 || block==2 || block==65 ||
            (block>2 && block<80 && next_random()%23==0);
        if(block>=80) {
            int32_t level=block<121?0:0x200000;
            int32_t phase=block<121?0:1;
            saw_wake |= specialized.engine.sleeping && phase!=0;
            ds_voice_gate(&specialized.engine,level,phase);
            ds_voice_gate(&reference,level,phase);
        }
        struct ds_params original;
        memcpy(&original,&specialized.params,sizeof(original));
        sf_render(&specialized);
        ds_voice_render(&reference,&original,specialized.trigger,expected,32);
        assert(!memcmp(expected,specialized.block,sizeof(expected)));
        assert(!memcmp(&reference,&specialized.engine,sizeof(reference)));
        assert(!memcmp(&original,&specialized.params,sizeof(original)));
        for(unsigned i=0;i<32;++i) {
            /* This upstream invariant makes sf_next's signed >>16 exact,
             * including negative samples that division truncates to zero. */
            assert(((uint32_t)expected[i]&0xffffu)==0);
            assert(expected[i]/65536==(expected[i]>>16));
        }
        saw_sleep |= specialized.engine.sleeping;
        ++calls;
    }
    assert(saw_sleep && saw_wake);
    printf("[ok] %u FUSE blocks match generic upstream PCM and complete engine state\n",calls);
}

static void reset(unsigned t) {
    memset(&sf_voices[t],0,sizeof(sf_voices[t]));
    ds_voice_init(&sf_voices[t].engine);
    sf_voices[t].trigger=1;sf_voices[t].pos=32;sf_active[t]=1;
}
int main(int argc, char **argv) {
    test_specialized_engine();
    assert(sf_marker("../AUDIO/FMSYNTH-SOPHIE.wav"));
    assert(sf_marker("FMSYNTH-SOPHIE-test.wav"));
    assert(!sf_marker("FMSYNTH.wav"));
    assert(!sf_marker("FMSYNTH-SOPHIEish.wav"));
    assert(!sf_marker("FMSYNTH-SOPHIE/normal.wav"));
    assert(!sf_marker(NULL));
    char longname[256];memset(longname,'a',sizeof(longname));
    assert(!sf_marker(longname));
    /* Every possible 16-bit source-sample difference stays within one PCM
     * unit of the old exact /147 interpolation, including negative slopes. */
    for (int difference=-65535;difference<=65535;++difference)
        for (unsigned fraction=0;fraction<147;++fraction) {
            int32_t exact=difference*(int32_t)fraction/147;
            int32_t fast=sf_interpolate(difference,fraction);
            int32_t error=fast-exact;
            assert(error>=-1 && error<=1);
        }
    uint32_t state[32]={0};uint16_t fp[6]={0x4000,0x3200,0x5000,0x4000,0x3000,0x4000};
    state[3]=25480119;state[6]=32768;*(uint16_t *)((uint8_t *)state+38)=32768;
    reset(0);reset(1);
    int32_t *audio=calloc(44100*2,sizeof(*audio));assert(audio);
    for (unsigned n=0;n<44100;) {
        unsigned count=44100-n<16?44100-n:16;
        assert(sf_fill(0,(uint8_t *)state,fp,audio+n*2,count));n+=count;
    }
    /* Independently render upstream at 48 kHz, then resample by absolute
     * sample index. This catches phase, fractional rate, gain and cadence. */
    int32_t *oracle=calloc(48100,sizeof(*oracle));assert(oracle);
    struct ds_voice voice;ds_voice_init(&voice);
    struct ds_params params={.phase_inc=(uint16_t)((state[3]>>8)*147/40960),
        .model=0,.color=50,.metal=80,.feedback=48,.velocity=127,.sweep=0,.fold=0};
    for (unsigned n=0;n<48096;n+=32)ds_voice_render(&voice,&params,n==0,oracle+n,32);
    uint32_t step=sf_voices[0].resample_step;
    uint32_t max_pcm_delta=0;
    for (unsigned n=0;n<44100;++n) {
        uint64_t at=(uint64_t)n*step;
        unsigned pos=(unsigned)(at/(147u*65536u));
        unsigned frac=(unsigned)((at%(147u*65536u))>>16);
        int32_t left=oracle[pos]/65536,right=oracle[pos+1]/65536;
        int32_t expected=2*(left+(right-left)*(int32_t)frac/147)*65536;
        int64_t delta=(int64_t)audio[2*n]-expected;
        if (delta<0) delta=-delta;
        if ((uint32_t)(delta/65536)>max_pcm_delta)
            max_pcm_delta=(uint32_t)(delta/65536);
        assert(delta<=2*65536 && audio[2*n+1]==audio[2*n]);
    }
    /* Arbitrary source-call splits retain the same continuous resampler. */
    for (unsigned n=0;n<44100;) {
        unsigned count=(n%11)+1;if(count>44100-n)count=44100-n;
        int32_t small[64]={0};assert(sf_fill(1,(uint8_t *)state,fp,small,count));
        assert(!memcmp(small,audio+n*2,count*2*sizeof(*small)));n+=count;
    }
    /* A one-cent change in either direction formerly vanished when all
     * three notes rounded to the same upstream integer phase increment. */
    uint32_t cents[3]={25486351u,25501083u,25515815u};
    int32_t tuned[3][4096];
    for (unsigned t=0;t<3;++t) {
        uint32_t lane[32];memcpy(lane,state,sizeof(lane));lane[3]=cents[t];
        reset(t+2);
        for (unsigned n=0;n<2048;n+=16)
            assert(sf_fill(t+2,(uint8_t *)lane,fp,tuned[t]+n*2,16));
    }
    assert(sf_voices[2].params.phase_inc==sf_voices[3].params.phase_inc);
    assert(sf_voices[3].params.phase_inc==sf_voices[4].params.phase_inc);
    assert(sf_voices[2].resample_step<sf_voices[3].resample_step);
    assert(sf_voices[3].resample_step<sf_voices[4].resample_step);
    assert(memcmp(tuned[0],tuned[1],sizeof(tuned[0])));
    assert(memcmp(tuned[1],tuned[2],sizeof(tuned[0])));
    uint32_t low_cents[3]={4883398u,4886221u,4889044u};
    uint32_t low_step[3], low_phase[3];
    for (unsigned t=0;t<3;++t) {
        uint32_t lane[32];memcpy(lane,state,sizeof(lane));lane[3]=low_cents[t];
        reset(t+2);
        assert(sf_fill(t+2,(uint8_t *)lane,fp,tuned[t],16));
        low_phase[t]=sf_voices[t+2].params.phase_inc;
        low_step[t]=sf_voices[t+2].resample_step;
    }
    assert(low_phase[0]==low_phase[1] && low_phase[1]==low_phase[2]);
    assert(low_step[0]<low_step[1] && low_step[1]<low_step[2]);
    /* Pitch conversion is cached only while the live PTCH/FINE word stays
     * unchanged, including cents that share one integer engine increment. */
    {
        uint32_t lane[32];memcpy(lane,state,sizeof(lane));
        int32_t block[32];
        reset(5);
        lane[3]=cents[0];
        assert(sf_fill(5,(uint8_t *)lane,fp,block,16));
        uint16_t first_phase=sf_voices[5].params.phase_inc;
        uint32_t first_step=sf_voices[5].resample_step;
        lane[3]=cents[2];
        assert(sf_fill(5,(uint8_t *)lane,fp,block,16));
        assert(sf_voices[5].params.phase_inc==first_phase);
        assert(sf_voices[5].resample_step>first_step);
        lane[3]=30000000u;
        assert(sf_fill(5,(uint8_t *)lane,fp,block,16));
        assert(sf_voices[5].params.phase_inc>first_phase);
    }
    /* Unselected track is an exact bypass; polyphonic Sophie fails silent. */
    int32_t untouched[32];for(unsigned i=0;i<32;++i)untouched[i]=123456;
    assert(!sf_fill(7,(uint8_t *)state,fp,untouched,16));
    for(unsigned i=0;i<32;++i)assert(untouched[i]==123456);
    ((uint8_t *)state)[80]=1;
    assert(sf_fill(1,(uint8_t *)state,fp,untouched,16));
    for(unsigned i=0;i<32;++i)assert(!untouched[i]);
    assert(sf_unsupported[1]==1 && sf_samples[7]==0);
    if(argc==2){FILE *f=fopen(argv[1],"wb");assert(f);assert(fwrite(audio,sizeof(*audio),88200,f)==88200);fclose(f);}
    free(audio);free(oracle);
    printf("[ok] Sophie resampler within %u PCM units of exact division; bipolar fine, 6 dB gain, split blocks and mono boundary\n",max_pcm_delta);
    return 0;
}
