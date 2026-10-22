/* Host sanitizer tests; Python separately checks the serialized CRC/layout. */
#include "storage.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static EulBank source, decoded, sentinel;
static uint8_t file[EUL_FILE_BYTES+1], altered[EUL_FILE_BYTES+1];

static void must_refuse(unsigned size) {
    memcpy(decoded,sentinel,sizeof(decoded));
    assert(!eul_file_decode(decoded,altered,size));
    assert(!memcmp(decoded,sentinel,sizeof(decoded)));
}
int main(int argc,char **argv) {
    memset(sentinel,0xa5,sizeof(sentinel));
    if (argc==3 && !strcmp(argv[1],"--refuse")) {
        FILE *input=fopen(argv[2],"rb"); assert(input);
        size_t size=fread(altered,1,sizeof(altered),input);
        assert(!ferror(input)); assert(!fclose(input));
        must_refuse((unsigned)size);
        return 0;
    }
    assert(argc==2);
    assert(eul_file_encode(file,EUL_FILE_BYTES,source));
    assert(eul_file_decode(decoded,file,EUL_FILE_BYTES));
    assert(!memcmp(source,decoded,sizeof(source)));
    puts("PASS: absent settings round-trip without materializing defaults");

    for (unsigned p=0;p<EUL_PARTS;++p) for (unsigned lane=0;lane<EUL_LANES;++lane) {
        EulParams *r=&source[p][lane];
        eul_defaults(r);
        r->steps=(uint8_t)(1+(p*7+lane)%16);
        r->pulses=(uint8_t)((p+lane)%(r->steps+1));
        r->rotate=(uint8_t)(lane%r->steps);
        r->mode=(uint8_t)((p+lane)%8);
        r->attack=(uint8_t)((p*19+lane)%128);
        r->decay=(uint8_t)((p*23+lane)%128);
        r->accents=(uint8_t)(lane%(r->pulses+1));
        r->accent_rotate=(uint8_t)(r->pulses ? p%r->pulses : 0);
        r->boost=(uint8_t)((p*31+lane)%128);
        r->swing=(uint8_t)((p+lane)%31);
    }
    assert(eul_file_encode(file,EUL_FILE_BYTES,source));
    assert(eul_file_decode(decoded,file,EUL_FILE_BYTES));
    assert(!memcmp(source,decoded,sizeof(source)));
    puts("PASS: all 48 audio/MIDI lanes and eight working/saved Part records round-trip");
    FILE *fixture=fopen(argv[1],"wb"); assert(fixture);
    assert(fwrite(file,1,EUL_FILE_BYTES,fixture)==EUL_FILE_BYTES);
    assert(!fclose(fixture));

    memcpy(altered,file,sizeof(file));
    for (unsigned size=0;size<EUL_FILE_BYTES;++size) must_refuse(size);
    must_refuse(EUL_FILE_BYTES+1);
    must_refuse(0xffffffffu);
    for (unsigned i=0;i<EUL_FILE_BYTES;++i) for (unsigned bit=0;bit<8;++bit) {
        altered[i]^=(uint8_t)(1u<<bit);
        must_refuse(EUL_FILE_BYTES);
        altered[i]^=(uint8_t)(1u<<bit);
    }
    puts("PASS: every truncated size, excess bytes and every single-bit mutation refused atomically");

    /* Bad in-memory records cannot be serialized. Include an invalid final
     * record to prove validation precedes even the first output write. */
    EulParams good=source[7][47];
    const unsigned fields[]={0,1,2,3,4,5,6,7,8,9};
    for (unsigned j=0;j<10;++j) {
        source[7][47]=good;
        ((uint8_t *)&source[7][47])[fields[j]]=255;
        memset(altered,0xa5,sizeof(altered));
        assert(!eul_file_encode(altered,EUL_FILE_BYTES,source));
        for (unsigned i=0;i<sizeof(altered);++i) assert(altered[i]==0xa5);
    }
    source[7][47]=good; source[7][47].steps=0;
    assert(!eul_file_encode(altered,EUL_FILE_BYTES,source));
    source[7][47]=good;
    assert(!eul_file_encode(altered,EUL_FILE_BYTES-1,source));
    assert(!eul_file_encode(altered,EUL_FILE_BYTES+1,source));
    puts("PASS: invalid records and wrong output sizes cannot partially encode");
    return 0;
}
