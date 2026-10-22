/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "adapter.c"

static void reset(unsigned t) {
    memset(&sf_voices[t],0,sizeof(sf_voices[t]));
    ds_voice_init(&sf_voices[t].engine);
    sf_voices[t].trigger=1;sf_voices[t].pos=32;sf_active[t]=1;
}
int main(int argc, char **argv) {
    assert(sf_marker("../AUDIO/FMSYNTH-SOPHIE.wav"));
    assert(sf_marker("FMSYNTH-SOPHIE-test.wav"));
    assert(!sf_marker("FMSYNTH.wav"));
    assert(!sf_marker("FMSYNTH-SOPHIEish.wav"));
    assert(!sf_marker("FMSYNTH-SOPHIE/normal.wav"));
    assert(!sf_marker(NULL));
    char longname[256];memset(longname,'a',sizeof(longname));
    assert(!sf_marker(longname));
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
    for (unsigned n=0;n<44100;++n) {
        uint64_t at=(uint64_t)n*step;
        unsigned pos=(unsigned)(at/(147u*65536u));
        unsigned frac=(unsigned)((at%(147u*65536u))>>16);
        int32_t left=oracle[pos]/65536,right=oracle[pos+1]/65536;
        int32_t expected=2*(left+(right-left)*(int32_t)frac/147)*65536;
        assert(audio[2*n]==expected && audio[2*n+1]==expected);
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
    puts("[ok] upstream/fractional-resampler oracle, bipolar fine, 6 dB gain, split blocks and mono boundary");
    return 0;
}
