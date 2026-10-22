/* Independent boundary/count oracles; also run under address/UB sanitizers. */
#include "engine.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static unsigned bits(unsigned x) {
    unsigned n=0; for (;x;x>>=1) n+=x&1; return n;
}
static unsigned phase(unsigned step,unsigned n) {
    /* Ceiling: sample on, not immediately before, the exact step boundary. */
    return (step*EUL_PHASE+n-1)/n;
}
int main(void) {
    for(unsigned steps=1;steps<=16;++steps) for(int sign=-1;sign<=1;++sign) {
        int32_t remainder=0;
        int64_t input=0,output=0;
        for(unsigned frame=0;frame<100000;++frame) {
            int32_t delta=sign*(int32_t)(frame%8191);
            input+=delta*16;
            output+=eul_clock(delta,steps,&remainder);
            assert(output==input/(int)steps);
            assert(remainder==input%(int)steps);
        }
    }
    puts("PASS: 4.8 million fixed-step clock cases, all lengths, forward/stopped/reverse, no odd-length drift");
    unsigned audio_cases=0;
    for(unsigned steps=1;steps<=16;++steps) for(unsigned mult=0;mult<=6;++mult)
    for(int sign=-1;sign<=1;++sign) {
        int32_t remainder=0;
        int64_t input=0,output=0,denominator=496125*steps;
        for(unsigned frame=0;frame<10000;++frame) {
            /* Tempo/speed modulation, including signed 16-bit extrema and
             * zero, all native MULTs, odd lengths and overflow boundary. */
            int speed=sign*(int)(frame%5==0?32767:frame%5==1?0:16384+frame%256);
            if(sign<0 && frame%5==0) speed=-32768;
            unsigned tempo=frame%4==0?8191:frame%4==1?2400:frame%4==2?2880:3288;
            input+=(int64_t)speed*tempo*8*(16u<<mult);
            output+=eul_audio_clock(speed,tempo,mult,steps,&remainder);
            assert(output==input/denominator);
            assert(remainder==input%denominator);
            ++audio_cases;
        }
        /* Changing direction and MULT must conserve the exact rational sum. */
        for(unsigned frame=0;frame<1000;++frame) {
            int speed=frame%3==0?-32768:frame%3==1?32767:0;
            unsigned shift=frame%7,tempo=frame%8192;
            input+=(int64_t)speed*tempo*8*(16u<<shift);
            output+=eul_audio_clock(speed,tempo,shift,steps,&remainder);
            assert(output*denominator+remainder==input);
            assert(remainder>-denominator && remainder<denominator);
            ++audio_cases;
        }
    }
    printf("PASS: %u exact audio-clock cases against independent 64-bit oracle; fractional SPD, tempo/MULT changes, reverse and bounds\n",audio_cases);
    EulParams p; eul_defaults(&p);
    uint16_t hits,accents;
    eul_masks(&p,&hits,&accents);
    assert(hits==0x49 && accents==0); /* 10010010, left to right in time */
    unsigned cases=0;
    for(unsigned n=1;n<=16;++n) for(unsigned k=0;k<=n;++k)
    for(unsigned r=0;r<n;++r) for(unsigned a=0;a<=k;++a)
    for(unsigned ar=0;ar<(k?k:1);++ar) {
        p.steps=n; p.pulses=k; p.rotate=r; p.accents=a; p.accent_rotate=ar;
        eul_masks(&p,&hits,&accents);
        unsigned expected_hits=0,expected_accents=0,ordinal=0;
        for(unsigned i=0;i<n;++i) if(k && (i*k)%n<k) {
            unsigned bit=1u<<((i+r)%n);
            expected_hits|=bit;
            if((((ordinal+k-ar)%k)*a)%k<a) expected_accents|=bit;
            ++ordinal;
        }
        assert(hits==expected_hits && accents==expected_accents);
        assert(bits(hits)==k && bits(accents)==a && !(accents&~hits));
        assert(!(hits>>n));
        if(k) {
            unsigned smallest=17,largest=0;
            for(unsigned i=0;i<n;++i) if(hits&(1u<<i)) {
                unsigned gap=1;
                while(!(hits&(1u<<((i+gap)%n)))) ++gap;
                if(gap<smallest) smallest=gap;
                if(gap>largest) largest=gap;
            }
            assert(largest-smallest<=1);
        }
        ++cases;
    }
    printf("PASS: %u rhythm/accent count, subset, rotation and spacing cases\n",cases);
    eul_defaults(&p); p.mode=EUL_GATE; p.decay=63;
    EulState s={0};
    for(unsigned i=0;i<8;++i) {
        int value=eul_process(&s,&p,phase(i,8),0,0,0);
        assert(value==((i==0||i==3||i==6)?(int)EUL_PHASE:0));
        assert(eul_process(&s,&p,phase(i,8)+EUL_PHASE/16,0,0,0)==0);
    }
    p.accents=1; p.boost=127;
    assert(eul_process(&s,&p,0,1,0,0)==2*EUL_PHASE);
    assert(eul_process(&s,&p,phase(3,8),0,0,0)==EUL_PHASE);
    p.accent_rotate=1;
    assert(eul_process(&s,&p,0,1,0,0)==EUL_PHASE);
    assert(eul_process(&s,&p,phase(3,8),0,0,0)==2*EUL_PHASE);
    assert(eul_process(&s,&p,phase(3,8),0,1,0)==0);
    assert(eul_process(&s,&p,EUL_PHASE,0,0,0)==0);
    p.pulses=0; assert(eul_process(&s,&p,0,0,0,0)==0);
    puts("PASS: gate edges, accent gain and rotation, silence and one-shot endpoints");
    eul_defaults(&p); p.steps=8; p.pulses=1; p.rotate=3; p.mode=EUL_RAND;
    memset(&s,0,sizeof(s));
    eul_process(&s,&p,phase(7,8),0,0,0);
    unsigned rng=s.rng;
    eul_process(&s,&p,0,0,0,0); assert(s.rng==rng);
    eul_process(&s,&p,phase(3,8),0,0,0); assert(s.rng!=rng);
    p.mode=EUL_LOOP;
    int captured=eul_process(&s,&p,phase(3,8),0,0,0);
    rng=s.rng;
    for(unsigned cycle=0;cycle<5;++cycle) {
        eul_process(&s,&p,phase(7,8),0,0,0);
        eul_process(&s,&p,0,0,0,0);
        assert(eul_process(&s,&p,phase(3,8),0,0,0)==captured);
        assert(s.rng==rng);
    }
    puts("PASS: rotated random waits for a pulse across wrap; LOOP captures and repeats");
    eul_defaults(&p); p.steps=16; p.pulses=16; p.mode=EUL_GATE;
    p.decay=0; p.swing=30;
    memset(&s,0,sizeof(s));
    for(unsigned i=0;i<16;++i) {
        unsigned pos=i*4096u+((i&1)?30*4096u/50:0);
        unsigned ph=pos*2048u/16;
        assert(eul_process(&s,&p,ph,0,0,0)==EUL_PHASE);
        if(i) assert(eul_process(&s,&p,ph-128,0,0,0)==0);
    }
    puts("PASS: exact swing boundaries, with no early pulse");
    /* Exercise every byte value as malformed input, every mode, both phase
     * directions, and full-scale gains under sanitizers. */
    for(unsigned byte=0;byte<256;++byte) for(unsigned mode=0;mode<8;++mode) {
        memset(&p,byte,sizeof(p)); p.mode=mode;
        memset(&s,0,sizeof(s));
        for(unsigned sample=0;sample<1024;++sample) {
            unsigned ph=(sample<512?sample:1023-sample)*(EUL_PHASE/512);
            int v=eul_process(&s,&p,ph,sample==0,0,47);
            assert(v>=-2*(int)EUL_PHASE && v<=2*(int)EUL_PHASE);
        }
    }
    puts("PASS: malformed settings, forward/reverse phase, all shapes within bounded output");
    for(unsigned field=0;field<sizeof(p);++field) {
        eul_defaults(&p);
        if(field==7) p.accents=1;
        uint8_t *bytes=(uint8_t *)&p;
        unsigned before=bytes[field];
        eul_edit(&p,field,1);
        assert(bytes[field]==before+1);
        eul_edit(&p,field,-1);
        assert(bytes[field]==before);
        for(unsigned i=0;i<128;++i) eul_edit(&p,field,127);
        EulParams maximum=p;
        assert(!eul_edit(&p,field,1));
        assert(!memcmp(&maximum,&p,sizeof(p)));
        for(unsigned i=0;i<128;++i) eul_edit(&p,field,-127);
        assert(bytes[field]==(field==0?1:0));
    }
    eul_defaults(&p); p.steps=16; p.pulses=16; p.accents=16;
    p.rotate=15; p.accent_rotate=15;
    eul_edit(&p,0,-12);
    assert(p.steps==4 && p.pulses==4 && p.accents==4 && p.rotate==3 && p.accent_rotate==3);
    puts("PASS: encoder unit increments, end stops, dependent clamping");
    for(unsigned mode=0;mode<4;++mode) {
        EulState positive={0},negative={0};
        eul_defaults(&p); p.mode=mode; p.accents=2; p.boost=127; p.attack=21;
        EulParams neg=p; neg.mode|=EUL_NEGATIVE;
        for(unsigned sample=0;sample<1024;++sample) {
            unsigned phase=(sample%256)*(EUL_PHASE/256);
            int a=eul_process(&positive,&p,phase,!phase,0,9);
            int b=eul_process(&negative,&neg,phase,!phase,0,9);
            assert(a==-b);
        }
        unsigned rng=positive.rng;
        int before=eul_process(&positive,&p,positive.phase,0,0,9);
        assert(eul_edit(&p,EUL_DIRECTION_FIELD,1));
        assert(p.mode==(mode|EUL_NEGATIVE));
        assert(!eul_edit(&p,EUL_DIRECTION_FIELD,127));
        assert(eul_process(&positive,&p,positive.phase,0,0,9)==-before);
        assert(positive.rng==rng);
        eul_edit(&p,3,127); assert(p.mode==(EUL_LOOP|EUL_NEGATIVE));
        eul_edit(&p,3,-127); assert(p.mode==EUL_NEGATIVE);
        eul_edit(&p,EUL_DIRECTION_FIELD,-1); assert(p.mode==EUL_ENV);
        assert(!eul_edit(&p,EUL_DIRECTION_FIELD,-127));
    }
    puts("PASS: DIR negates all shapes exactly, preserves random targets and survives shape edits");
    return 0;
}
