/* HMT2: own-step DEG/CHRD low ten bits, ACC next four, metadata top two.
 * Step 0 is the aligned commit word. Steps 1..63 carry 126 metadata bits:
 * version/state/status/generation/checksum (11 B), settings (4 B),
 * default amount (4 bits), reserved (2 bits). Expected bank/lane identity
 * is hashed rather than stored. Lane 0 commits last after the outer
 * generation recheck. Every lane validates before ANY runtime publication.
 */
#include "track-retention.h"
#define MARK 0x8000u
#define TOKEN 0x03ffu
#define DATA 0x3fffu

static volatile uint16_t *at(unsigned lane, unsigned step) {
    return (volatile uint16_t *)(uintptr_t)(0x1001614eu + (lane / 8u)*0x8ed8u +
        0x4900u + (lane % 8u)*0x8b0u + step*32u + 30u);
}
static void put32(uint8_t *p, uint32_t v) {
    p[0]=(uint8_t)(v>>24); p[1]=(uint8_t)(v>>16);
    p[2]=(uint8_t)(v>>8); p[3]=(uint8_t)v;
}
static uint32_t get32(const uint8_t *p) {
    return (uint32_t)p[0]<<24 | (uint32_t)p[1]<<16 | (uint32_t)p[2]<<8 | p[3];
}
static uint32_t hash(const uint8_t *p, unsigned n, uint32_t h) {
    while (n--) h=(h ^ *p++)*0x01000193u;
    return h;
}
void hd_track_invalidate_c(void) {
    *at(0,0) &= DATA;
}
int hd_track_write_c(const uint8_t *payload, unsigned bank, uint32_t ticket, unsigned status) {
    if (bank >= HD_BANKS || status > 4 || !hd_packed_valid_c(payload) ||
        !ha_valid_c(payload+HD_PAYLOAD_BYTES)) return 0;
    for (unsigned lane=0; lane<HD_LANES; ++lane) {
        const uint8_t *p=payload+lane*HD_PACKED_LANE;
        const uint8_t *a=payload+HD_PAYLOAD_BYTES+lane*HA_LANE_BYTES;
        uint8_t identity[2]={(uint8_t)bank,(uint8_t)lane};
        uint8_t h[16]={2,p[0],(uint8_t)status};
        put32(h+3,ticket);
        for (unsigned i=0;i<4;++i) h[11+i]=a[32+i];
        h[15]=(uint8_t)(a[36]<<4);
        uint32_t sum=hash(identity,2,0x811c9dc5u);
        sum=hash(h,7,sum); sum=hash(p,81,sum); sum=hash(a,37,sum);
        put32(h+7,sum);
        /* Four adjacent ten-bit tokens occupy five bytes. Each four-step
         * group also consumes two ACC bytes and one header byte; its first
         * metadata pair came from the preceding header byte. Step zero has
         * no header pair and remains uncommitted until the outer recheck. */
        const uint8_t *tokens=p+1, *amounts=a;
        volatile uint16_t *dst=at(lane,0);
        unsigned previous=0;
        for (unsigned group=0; group<HD_STEPS/4; ++group) {
            unsigned hbyte=h[group], x=amounts[0], y=amounts[1];
            dst[0]=(uint16_t)(((unsigned)tokens[0]<<2 | tokens[1]>>6) |
                             ((x&0xf0u)<<6) | (previous<<14));
            dst[16]=(uint16_t)((((unsigned)tokens[1]&63u)<<4 | tokens[2]>>4) |
                              ((x&15u)<<10) | ((hbyte&0xc0u)<<8));
            dst[32]=(uint16_t)((((unsigned)tokens[2]&15u)<<6 | tokens[3]>>2) |
                              ((y&0xf0u)<<6) | ((hbyte&0x30u)<<10));
            dst[48]=(uint16_t)((((unsigned)tokens[3]&3u)<<8 | tokens[4]) |
                              ((y&15u)<<10) | ((hbyte&0x0cu)<<12));
            previous=hbyte&3u;
            dst+=64; tokens+=5; amounts+=2;
        }
        if (lane) *at(lane,0) |= MARK;
    }
    return 1;
}
void hd_track_commit_c(void) {
    *at(0,0) |= MARK;
}
int hd_track_read_c(uint8_t *payload, unsigned bank, unsigned *status) {
    if (bank >= HD_BANKS || (*at(0,0) & ~DATA) != MARK) return 0;
    uint32_t generation=0;
    unsigned bank_status=0;
    for (unsigned lane=0; lane<HD_LANES; ++lane) {
        uint8_t h[16];
        uint8_t *p=payload+lane*HD_PACKED_LANE;
        uint8_t *a=payload+HD_PAYLOAD_BYTES+lane*HA_LANE_BYTES;
        uint8_t *tokens=p+1, *amounts=a;
        const volatile uint16_t *src=at(lane,0);
        for (unsigned group=0; group<HD_STEPS/4; ++group) {
            unsigned w=src[0], x=src[16], y=src[32], z=src[48];
            if (!group) { if ((w & ~DATA) != MARK) return 0; }
            else h[group-1]|=(uint8_t)(w>>14);
            h[group]=(uint8_t)(((x>>8)&0xc0u) | ((y>>10)&0x30u) | ((z>>12)&0x0cu));
            tokens[0]=(uint8_t)((w&TOKEN)>>2);
            tokens[1]=(uint8_t)((w<<6) | ((x&TOKEN)>>4));
            tokens[2]=(uint8_t)((x<<4) | ((y&TOKEN)>>6));
            tokens[3]=(uint8_t)((y<<2) | ((z&TOKEN)>>8));
            tokens[4]=(uint8_t)z;
            amounts[0]=(uint8_t)(((w>>6)&0xf0u) | ((x>>10)&15u));
            amounts[1]=(uint8_t)(((y>>6)&0xf0u) | ((z>>10)&15u));
            src+=64; tokens+=5; amounts+=2;
        }
        p[0]=h[1];
        for (unsigned i=0;i<4;++i) a[32+i]=h[11+i];
        a[36]=h[15]>>4;
        uint8_t identity[2]={(uint8_t)bank,(uint8_t)lane};
        uint32_t sum=hash(identity,2,0x811c9dc5u);
        sum=hash(h,7,sum); sum=hash(p,81,sum); sum=hash(a,37,sum);
        if (h[0]!=2 || h[2]>4 || (h[15]&15) || get32(h+7)!=sum) return 0;
        if (!lane) { generation=get32(h+3); bank_status=h[2]; }
        else if (get32(h+3)!=generation || h[2]!=bank_status) return 0;
    }
    if (!hd_packed_valid_c(payload) || !ha_valid_c(payload+HD_PAYLOAD_BYTES)) return 0;
    *status=bank_status;
    return 1;
}
