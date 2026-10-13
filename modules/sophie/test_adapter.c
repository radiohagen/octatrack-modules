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
     * sample index. This catches phase, rate, gain and block-cadence errors. */
    int32_t *oracle=calloc(48032,sizeof(*oracle));assert(oracle);
    struct ds_voice voice;ds_voice_init(&voice);
    struct ds_params params={.phase_inc=(uint16_t)((state[3]>>8)*147/40960),
        .model=0,.color=50,.metal=80,.feedback=48,.velocity=127,.sweep=0,.fold=0};
    for (unsigned n=0;n<48032;n+=32)ds_voice_render(&voice,&params,n==0,oracle+n,32);
    for (unsigned n=0;n<44100;++n) {
        unsigned pos=n*160/147,frac=n*160%147;
        int32_t left=oracle[pos]/65536,right=oracle[pos+1]/65536;
        int32_t expected=(left+(right-left)*(int32_t)frac/147)*65536;
        assert(audio[2*n]==expected && audio[2*n+1]==expected);
    }
    /* Arbitrary source-call splits retain the same continuous resampler. */
    for (unsigned n=0;n<44100;) {
        unsigned count=(n%11)+1;if(count>44100-n)count=44100-n;
        int32_t small[64]={0};assert(sf_fill(1,(uint8_t *)state,fp,small,count));
        assert(!memcmp(small,audio+n*2,count*2*sizeof(*small)));n+=count;
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
    puts("[ok] exact upstream/resampler oracle, split blocks, marker isolation and mono boundary");
    return 0;
}
