/* Final-pitch translation; native notes, Parts and producer packets are never
 * rewritten. The existing source ledger remains the release authority. */
#include "translation.h"

/* Explicit initialized storage: do not depend on the platform's BSS contents. */
#define DATA __attribute__((section(".data")))
uint8_t lt_work[LT_TABLE_BYTES] DATA = {0};
uint8_t lt_saved[LT_TABLE_BYTES] DATA = {0};
uint32_t lt_readonly DATA = 0, lt_dirty DATA = 0, lt_storage_busy DATA = 0;
static uint8_t pitches[2048][2] DATA = {{0}};
static uint16_t references[2][2048] DATA = {{0}};
static uint8_t owners[2048] DATA = {0}, translated[2048] DATA = {0};
static uint16_t translated_held[8] DATA = {0};
static const uint8_t preset[LT_FIELDS] = {0,60,84,12};
extern uint32_t lb_page_track;

static unsigned offset(unsigned context, unsigned track) {
    return (context*LT_TRACKS+track)*LT_RECORD;
}
int lt_get(unsigned context, unsigned track, unsigned field) {
    if (context>=LT_CONTEXTS || track>=LT_TRACKS || field>=LT_FIELDS) return -1;
    const uint8_t *p=lt_work+offset(context,track);
    return p[LT_FIELDS] ? p[field] : preset[field];
}
int lt_ui_get(unsigned track,unsigned field) {
    return lt_get((unsigned)lt_ui_context(),track,field);
}
int lt_ui_set(unsigned track,unsigned field,unsigned value) {
    return lt_set((unsigned)lt_ui_context(),track,field,value);
}
void lt_apply_format(char *buffer,unsigned value) {
    const char *name=value==1 ? "INT" : value==2 ? "EXT" : value==3 ? "BOTH" : "OFF";
    while ((*buffer++=*name++)) {}
}
void lt_number_format(char *buffer,unsigned value) {
    if (value>127) value=127;
    if (value>=100) *buffer++=(char)('0'+value/100);
    if (value>=10) *buffer++=(char)('0'+value/10%10);
    *buffer++=(char)('0'+value%10);*buffer=0;
}
void lt_note_format(char *buffer,unsigned value) {
    /* Explicit requested convention: MIDI 60 = C4, independent of native labels. */
    static const char names[12][2]={{'C',0},{'C','#'},{'D',0},{'D','#'},
        {'E',0},{'F',0},{'F','#'},{'G',0},{'G','#'},{'A',0},{'A','#'},{'B',0}};
    if (value>127) value=127;
    *buffer++=names[value%12][0];
    if (names[value%12][1]) *buffer++='#';
    int octave=(int)(value/12)-1;
    if (octave<0) { *buffer++='-';octave=-octave; }
    *buffer++=(char)('0'+octave);*buffer=0;
}
void lt_range_format(char *buffer,unsigned value) {
    *buffer++=(char)0xb1; /* Native small-font plus/minus glyph. */
    lt_number_format(buffer,value/2); /* Native dial position is twice the radius. */
}
void lt_flush_all(void) {
    for (unsigned track=0;track<LT_TRACKS;++track)
        if (translated_held[track]) lb_flush(track);
}
int lt_set(unsigned context, unsigned track, unsigned field, unsigned value) {
    if (lt_storage_busy || context>=LT_CONTEXTS || track>=LT_TRACKS ||
        field>=LT_FIELDS || value>(field==3 ? 63u : field ? 127u : 3u)) return 0;
    if (lt_readonly&(1u<<(context/4))) return 0;
    uint8_t record[LT_RECORD];
    for (unsigned i=0;i<LT_FIELDS;++i) record[i]=(uint8_t)lt_get(context,track,i);
    record[LT_FIELDS]=1;
    if (record[field]==value) return 1;
    unsigned was_enabled=record[0];
    record[field]=(uint8_t)value;
    uint16_t sr=lt_lock();
    /* Both sequenced and live ownership use this track. Release original
     * outputs before publishing a new mapping; late releases are tombstoned. */
    if (was_enabled || record[0]) lb_flush(track);
    uint8_t *p=lt_work+offset(context,track);
    for (unsigned i=0;i<LT_RECORD;++i) p[i]=record[i];
    lt_dirty|=1u<<(context/4);
    lt_mark_dirty(context);
    lt_unlock(sr);
    return 1;
}
int lt_map(int note, unsigned source, unsigned target, unsigned radius) {
    if (note<0 || note>127 || source>127 || target>127 || radius>63)
        return -1;
    int distance=note-(int)source, result=(int)target+distance;
    return distance<-(int)radius || distance>(int)radius || result<0 || result>127 ? -1 : result;
}
static uint32_t packet(unsigned index, unsigned destinations) {
    return destinations | (uint32_t)pitches[index][0]<<8 |
           (uint32_t)pitches[index][1]<<16;
}
uint32_t lt_prepare(unsigned index, unsigned track, unsigned destinations, unsigned ui) {
    if (index>=2048 || track>=8) return 0;
    unsigned note=index&127;
    owners[index]=(uint8_t)track;
    translated[index]=0;
    pitches[index][0]=pitches[index][1]=(uint8_t)note;
    int context=ui ? lt_ui_context() : lt_play_context(track);
    int apply=lt_get((unsigned)context,track,0);
    if (apply<=0) return packet(index,destinations);
    translated[index]=(uint8_t)((unsigned)apply&destinations);
    int mapped=lt_map((int)note,(unsigned)lt_get(context,track,1),
        (unsigned)lt_get(context,track,2),(unsigned)lt_get(context,track,3));
    for (unsigned d=0;d<2;++d) {
        unsigned bit=1u<<d;
        if (!((unsigned)apply&destinations&bit)) continue;
        if (mapped<0) destinations&=~bit;
        else pitches[index][d]=(uint8_t)mapped;
    }
    return packet(index,destinations);
}
uint32_t lt_commit(unsigned index, unsigned destinations) {
    if (index>=2048) return 0;
    unsigned emit=destinations;
    if (translated[index]&destinations) ++translated_held[owners[index]];
    else translated[index]=0;
    for (unsigned d=0;d<2;++d) if (destinations&(1u<<d)) {
        unsigned target=(index&~127u)+pitches[index][d];
        /* Different source pitches can map onto one destination pitch.
         * Coalesce the destination voice and release only its final owner. */
        if (references[d][target]++) emit&=~(1u<<d);
    }
    return packet(index,emit);
}
uint32_t lt_release(unsigned index, unsigned destinations) {
    if (index>=2048) return 0;
    unsigned emit=destinations;
    if (translated[index]) {
        --translated_held[owners[index]];
        translated[index]=0;
    }
    for (unsigned d=0;d<2;++d) if (destinations&(1u<<d)) {
        unsigned target=(index&~127u)+pitches[index][d];
        if (!references[d][target] || --references[d][target]) emit&=~(1u<<d);
    }
    return packet(index,emit);
}
uint32_t lt_duplicate(unsigned index, unsigned destinations) {
    return index<2048 ? packet(index,destinations&2) : 0;
}
int lt_valid(const uint8_t *payload, unsigned length) {
    if (length!=LT_PAYLOAD_BYTES && length!=8*LT_PART_BYTES) return 0;
    for (unsigned at=0;at<length;at+=LT_RECORD) {
        const uint8_t *p=payload+at;
        if (!p[LT_FIELDS]) {
            for (unsigned f=0;f<LT_FIELDS;++f) if (p[f]) return 0;
        } else if (p[LT_FIELDS]!=1 || p[0]>3 || p[1]>127 || p[2]>127 || p[3]>63) return 0;
    }
    return 1;
}
void lt_reset(void) {
    lt_flush_all();
    for (unsigned i=0;i<LT_TABLE_BYTES;++i) lt_work[i]=lt_saved[i]=0;
    lt_readonly=0;
    lt_dirty=0;
}

/* Native Part copy/initialization integration is implemented at the same
 * coherent boundary as Part State, never by parsing a native file. */
/* Native Part paste/undo sources at 0x40029b54 and 0x40029b8a.
 * Keep parallel transient records only for those two native clipboards. */
static uint8_t clipboard[2][LT_PART_BYTES] DATA = {{0}};
static uint8_t *part(unsigned address) {
    if (address==0x460bf218u) return clipboard[0];
    if (address==0x460c8122u) return clipboard[1];
    if (address<0x400e21e0u || address>=0x400e21e0u+16u*0x9b340u) return 0;
    unsigned rel=address-0x400e21e0u, bank=rel/0x9b340u;
    rel%=0x9b340u;
    unsigned saved=rel>=0x9504au;
    unsigned base=saved ? 0x9504au : 0x8ed80u;
    if (rel<base || rel>=base+4u*0x18b2u || (rel-base)%0x18b2u) return 0;
    unsigned context=bank*4u+(rel-base)/0x18b2u;
    return (saved ? lt_saved : lt_work)+context*LT_PART_BYTES;
}
void lt_part_copy(unsigned destination, unsigned source, unsigned length) {
    if (length!=0x18b2u || source==destination) return;
    uint8_t *dst=part(destination), *src=part(source);
    if (!dst || !src) return; /* disk/bulk loads are handled by STORE */
    uint16_t sr=lt_lock();
    if ((uintptr_t)dst>=(uintptr_t)lt_work && (uintptr_t)dst<(uintptr_t)lt_work+LT_TABLE_BYTES) {
        for (unsigned t=0;t<8;++t)
            if (dst[t*LT_RECORD] || src[t*LT_RECORD]) lb_flush(t);
    }
    for (unsigned i=0;i<LT_PART_BYTES;++i) dst[i]=src[i];
    if (destination<0x400e21e0u+16u*0x9b340u)
        lt_dirty|=1u<<((destination-0x400e21e0u)/0x9b340u);
    lt_unlock(sr);
}
void lt_part_init(unsigned destination) {
    uint8_t *dst=part(destination);
    if (!dst) return;
    uint16_t sr=lt_lock();
    if ((uintptr_t)dst>=(uintptr_t)lt_work && (uintptr_t)dst<(uintptr_t)lt_work+LT_TABLE_BYTES)
        for (unsigned t=0;t<8;++t) if (dst[t*LT_RECORD]) lb_flush(t);
    for (unsigned i=0;i<LT_PART_BYTES;++i) dst[i]=0;
    if (destination<0x400e21e0u+16u*0x9b340u)
        lt_dirty|=1u<<((destination-0x400e21e0u)/0x9b340u);
    lt_unlock(sr);
}
