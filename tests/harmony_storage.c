/* Independent bit-at-a-time oracles for the production packed/HMT2 codecs.
 * The Python runner redirects only the fixed SRAM base to this host buffer. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "packed.h"
#include "track-retention.h"

uint8_t retained_test_memory[0xa0000];
static uint8_t touched[sizeof retained_test_memory];
static HdBank roots, restored;
static uint8_t qualities[HD_LOCKS], restored_q[HD_LOCKS];
static uint8_t payload[HD_TRACK_PAYLOAD_BYTES], output[HD_TRACK_PAYLOAD_BYTES];

/* Root conversion is not exercised by either codec. */
int hd_encode_c(int note, int scale) { (void)note; (void)scale; assert(0); return -1; }
int hd_decode_c(int degree, int scale) { (void)degree; (void)scale; assert(0); return -1; }
/* ACC format validation is independent of its hardware-owned runtime. */
int ha_valid_c(const volatile uint8_t *p) {
    for (unsigned lane=0; lane<HD_LANES; ++lane,p+=HA_LANE_BYTES)
        if ((int8_t)p[32]<-21 || (int8_t)p[32]>0 || p[33]>21 ||
            p[34]>3 || p[35]>3 || p[36]<1 || p[36]>15) return 0;
    return 1;
}
static unsigned mirror(unsigned d) {
    static const int offsets[7]={0,2,4,5,7,9,11};
    if (d==255) return 255;
    int n=((int)(d/7)-1)*12+offsets[d%7];
    return (unsigned)(n<0 ? 0 : n>127 ? 127 : n);
}
static void bits_put(uint8_t *p, unsigned bit, unsigned n, unsigned v) {
    for (unsigned i=0;i<n;++i) {
        unsigned shift=7-(bit+i)%8, byte=(bit+i)/8;
        p[byte]=(uint8_t)((p[byte]&~(1u<<shift)) | (((v>>(n-1-i))&1u)<<shift));
    }
}
static unsigned bits_get(const uint8_t *p, unsigned bit, unsigned n) {
    unsigned v=0;
    for (unsigned i=0;i<n;++i) v=(v<<1) | ((p[(bit+i)/8]>>(7-(bit+i)%8))&1u);
    return v;
}
static void put32(uint8_t *p,uint32_t v) {
    for (unsigned i=0;i<4;++i) p[i]=(uint8_t)(v>>(24-8*i));
}
static uint32_t fnv(const uint8_t *p,unsigned n,uint32_t hash) {
    for (unsigned i=0;i<n;++i) hash=(hash^p[i])*0x1000193u;
    return hash;
}
static uint16_t *word(unsigned lane,unsigned step) {
    return (uint16_t *)(void *)(retained_test_memory+(lane/8)*0x8ed8u+
                               0x4900u+(lane%8)*0x8b0u+step*32u+30u);
}
static void seed(unsigned shift) {
    memset(payload,0,sizeof payload);
    for (unsigned lane=0;lane<HD_LANES;++lane) {
        HdRoots *r=&roots.roots[lane];
        unsigned state=(lane+shift)%3;
        r->state=(uint8_t)state; r->scale=(uint8_t)(lane%84);
        r->context=state ? (uint8_t)(lane%64) : 255;
        payload[lane*HD_PACKED_LANE]=(uint8_t)(state*84+r->scale);
        for (unsigned step=0;step<HD_STEPS;++step) {
            unsigned t=(lane*64+step+shift)%765,d=t/9,q=t%9;
            d=state==2 && d<84 ? d : 255;
            r->degree[step]=(uint8_t)d;
            r->note[step]=(uint8_t)(state==1 ? step*2 : mirror(d));
            qualities[lane*64+step]=(uint8_t)(q==8 ? 255 : q);
            bits_put(payload+lane*81+1,step*10,10,(d==255 ? 84 : d)*9+q);
        }
        uint8_t *a=payload+HD_PAYLOAD_BYTES+lane*HA_LANE_BYTES;
        for (unsigned i=0;i<32;++i) a[i]=(uint8_t)(i*37+lane+shift);
        a[32]=(uint8_t)(-(int)(lane%22)); a[33]=(uint8_t)(lane%22);
        a[34]=(uint8_t)(lane%4); a[35]=(uint8_t)((lane+1)%4); a[36]=(uint8_t)(lane%15+1);
    }
}
static void packed_test(void) {
    for (unsigned shift=0;shift<3;++shift) {
        seed(shift);
        assert(hd_pack_c(&roots,qualities,output)==1);
        assert(!memcmp(output,payload,HD_PAYLOAD_BYTES));
        assert(hd_unpack_c(&restored,restored_q,payload)==1);
        assert(!memcmp(qualities,restored_q,sizeof qualities));
        for (unsigned lane=0;lane<HD_LANES;++lane) {
            const HdRoots *r=&restored.roots[lane],*before=&roots.roots[lane];
            assert(r->state==before->state && r->scale==before->scale && r->context==255);
            assert(!memcmp(r->degree,before->degree,HD_STEPS));
            for (unsigned step=0;step<HD_STEPS;++step) assert(r->note[step]==mirror(r->degree[step]));
        }
    }
    /* Exhaust every ten-bit value at each alignment, in all root states.
     * Invalid payloads must preserve both entire destination buffers. */
    seed(0);
    for (unsigned state=0;state<3;++state) for (unsigned position=0;position<4;++position) {
        payload[0]=(uint8_t)(state*84);
        for (unsigned t=0;t<1024;++t) {
            bits_put(payload+1,position*10,10,t);
            int valid=t<765 && (state==2 || t>=756);
            assert(hd_packed_valid_c(payload)==valid);
            memset(&restored,0xcc,sizeof restored); memset(restored_q,0xdd,sizeof restored_q);
            assert(hd_unpack_c(&restored,restored_q,payload)==valid);
            if (valid) {
                assert(restored.roots[0].degree[position]==(t/9==84 ? 255 : t/9));
                assert(restored_q[position]==(t%9==8 ? 255 : t%9));
            } else {
                for (unsigned i=0;i<sizeof restored;++i) assert(((uint8_t *)&restored)[i]==0xcc);
                for (unsigned i=0;i<sizeof restored_q;++i) assert(restored_q[i]==0xdd);
            }
        }
        bits_put(payload+1,position*10,10,764);
    }
    /* Reject corruption after every earlier lane has been validated, without
     * publishing those earlier lanes into either destination. */
    uint8_t *last=payload+(HD_LANES-1)*HD_PACKED_LANE+1;
    unsigned last_bit=(HD_STEPS-1)*10, saved=bits_get(last,last_bit,10);
    bits_put(last,last_bit,10,1023);
    assert(hd_packed_valid_c(payload)==0);
    memset(&restored,0xcc,sizeof restored); memset(restored_q,0xdd,sizeof restored_q);
    assert(hd_unpack_c(&restored,restored_q,payload)==0);
    for (unsigned i=0;i<sizeof restored;++i) assert(((uint8_t *)&restored)[i]==0xcc);
    for (unsigned i=0;i<sizeof restored_q;++i) assert(restored_q[i]==0xdd);
    bits_put(last,last_bit,10,saved);
    for (unsigned meta=0;meta<256;++meta) {
        payload[0]=(uint8_t)meta;
        assert(hd_packed_valid_c(payload)==(meta<252));
    }
    payload[0]=168;
    assert(hd_unpack_c(0,0,payload)==1);
    assert(hd_unpack_c(0,restored_q,payload)==1);
    assert(hd_unpack_c(&restored,0,payload)==1);
}
static int packable(void) {
    for (unsigned lane=0;lane<HD_LANES;++lane) {
        const HdRoots *r=&roots.roots[lane];
        if (!hd_roots_valid_c(r)) return 0;
        for (unsigned step=0;step<HD_STEPS;++step) {
            unsigned q=qualities[lane*HD_STEPS+step];
            if ((q>7 && q!=255) ||
                (r->state==HD_ROOT_HARM && r->note[step]!=mirror(r->degree[step]))) return 0;
        }
    }
    return 1;
}
static void pack_validation_test(void) {
    /* The fused packer must retain all root metadata/step validity rules.
     * Exercise the full byte domain for each field type in every state. */
    seed(0);
    for (unsigned state=0;state<3;++state) {
        HdRoots *r=&roots.roots[state];
        uint8_t *fields[]={&r->degree[0],&r->note[0],&r->state,&r->scale,&r->context,
                          &qualities[state*HD_STEPS]};
        for (unsigned field=0;field<sizeof fields/sizeof fields[0];++field) {
            uint8_t old=*fields[field];
            for (unsigned value=0;value<256;++value) {
                *fields[field]=(uint8_t)value;
                assert(hd_pack_c(&roots,qualities,output)==packable());
            }
            *fields[field]=old;
        }
    }
}
static void expected_header(uint8_t *h,unsigned lane,unsigned bank,uint32_t generation,unsigned status) {
    const uint8_t *p=payload+lane*HD_PACKED_LANE;
    const uint8_t *a=payload+HD_PAYLOAD_BYTES+lane*HA_LANE_BYTES;
    uint8_t identity[2]={(uint8_t)bank,(uint8_t)lane};
    memset(h,0,16); h[0]=2; h[1]=p[0]; h[2]=(uint8_t)status;
    put32(h+3,generation);
    uint32_t hash=fnv(identity,2,0x811c9dc5u);
    hash=fnv(h,7,hash); hash=fnv(p,81,hash); hash=fnv(a,37,hash);
    put32(h+7,hash); memcpy(h+11,a+32,4); h[15]=(uint8_t)(a[36]<<4);
}
static void retention_test(void) {
    for (unsigned run=0;run<3;++run) {
        unsigned bank=run ? 16-run : 0, status=run*2, read_status=99;
        uint32_t generation=0xfedcba98u+run;
        seed(run);
        memset(retained_test_memory,0xa5,sizeof retained_test_memory);
        memset(touched,0,sizeof touched);
        assert(hd_track_write_c(payload,bank,generation,status)==1);
        assert(hd_track_read_c(output,bank,&read_status)==0 && read_status==99);
        hd_track_commit_c();
        for (unsigned lane=0;lane<HD_LANES;++lane) {
            uint8_t h[16]; expected_header(h,lane,bank,generation,status);
            for (unsigned step=0;step<HD_STEPS;++step) {
                unsigned token=bits_get(payload+lane*81+1,step*10,10);
                unsigned acc=bits_get(payload+HD_PAYLOAD_BYTES+lane*37,step*4,4);
                unsigned meta=step ? bits_get(h,(step-1)*2,2) : 2;
                uint16_t *w=word(lane,step);
                assert(*w==(token | (acc<<10) | (meta<<14)));
                size_t offset=(uint8_t *)w-retained_test_memory;
                touched[offset]=touched[offset+1]=1;
            }
        }
        for (unsigned i=0;i<sizeof touched;++i) if (!touched[i]) assert(retained_test_memory[i]==0xa5);
        assert(hd_track_read_c(output,bank,&read_status)==1 && read_status==status);
        assert(!memcmp(output,payload,sizeof payload));
        assert(hd_track_read_c(output,bank^1,&read_status)==0);
        for (unsigned lane=0;lane<HD_LANES;++lane) {
            *word(lane,lane%64)^=1;
            assert(hd_track_read_c(output,bank,&read_status)==0);
            *word(lane,lane%64)^=1;
        }
        hd_track_invalidate_c();
        assert(hd_track_read_c(output,bank,&read_status)==0);
    }
    assert(hd_track_write_c(payload,16,1,0)==0);
    assert(hd_track_write_c(payload,0,1,5)==0);
    assert(hd_track_read_c(output,16,(unsigned[]){0})==0);
}
int main(void) {
    packed_test(); pack_validation_test(); retention_test();
    puts("Harmony packed/HMT2: exhaustive token validity, exact bytes, all 8192 step addresses, corruption and publication guards passed");
    return 0;
}
