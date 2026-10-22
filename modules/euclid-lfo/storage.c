/* Sidecar codec, deliberately independent of native file/STORE plumbing. */
#include "storage.h"

_Static_assert(sizeof(EulParams)==10, "EULF v1 requires ten-byte records");
_Static_assert(sizeof(EulBank)==EUL_BANK_BYTES, "EULF v1 bank layout changed");

static uint32_t eul_read_be32(const uint8_t *p) {
    return (uint32_t)p[0]<<24 | (uint32_t)p[1]<<16 |
           (uint32_t)p[2]<<8 | p[3];
}
static void eul_write_be32(uint8_t *p,uint32_t n) {
    p[0]=(uint8_t)(n>>24); p[1]=(uint8_t)(n>>16);
    p[2]=(uint8_t)(n>>8); p[3]=(uint8_t)n;
}
/* zlib/STORE CRC-32, with the same incremental finalized-CRC convention. */
uint32_t eul_crc32(const uint8_t *p,unsigned size,uint32_t crc) {
    crc=~crc;
    while (size--) {
        crc^=*p++;
        for (unsigned bit=0;bit<8;++bit)
            crc=(crc>>1) ^ ((0u-(crc&1u))&0xedb88320u);
    }
    return ~crc;
}
unsigned eul_record_valid(const uint8_t *p) {
    if (!p[0]) {
        /* Only the all-zero record is absent. Never hide malformed bytes
         * behind the engine's defensive default handling. */
        for (unsigned i=1;i<10;++i) if (p[i]) return 0;
        return 1;
    }
    return p[0]<=EUL_STEPS && p[1]<=p[0] && p[2]<p[0] &&
           p[3]<=(EUL_LOOP|EUL_NEGATIVE) && p[4]<=127 && p[5]<=127 && p[6]<=p[1] &&
           (p[1] ? p[7]<p[1] : p[7]==0) && p[8]<=127 && p[9]<=30;
}
static unsigned eul_payload_valid(const uint8_t *p) {
    for (unsigned i=0;i<EUL_BANK_BYTES;i+=10)
        if (!eul_record_valid(p+i)) return 0;
    return 1;
}
unsigned eul_file_encode(uint8_t *out,unsigned size,const EulBank bank) {
    const uint8_t *payload=(const uint8_t *)bank;
    if (size!=EUL_FILE_BYTES || !eul_payload_valid(payload)) return 0;
    out[0]='E'; out[1]='U'; out[2]='L'; out[3]='F';
    eul_write_be32(out+4,1);
    eul_write_be32(out+8,EUL_BANK_BYTES);
    for (unsigned i=0;i<EUL_BANK_BYTES;++i) out[16+i]=payload[i];
    eul_write_be32(out+12,eul_crc32(out+16,EUL_BANK_BYTES,eul_crc32(out,12,0)));
    return 1;
}
unsigned eul_file_decode(EulBank out,const uint8_t *file,unsigned size) {
    if (size!=EUL_FILE_BYTES) return 0;
    if (file[0]!='E' || file[1]!='U' || file[2]!='L' || file[3]!='F' ||
        eul_read_be32(file+4)!=1 || eul_read_be32(file+8)!=EUL_BANK_BYTES)
        return 0;
    if (eul_read_be32(file+12)!=
        eul_crc32(file+16,EUL_BANK_BYTES,eul_crc32(file,12,0)) ||
        !eul_payload_valid(file+16)) return 0;
    uint8_t *payload=(uint8_t *)out;
    for (unsigned i=0;i<EUL_BANK_BYTES;++i) payload[i]=file[16+i];
    return 1;
}
