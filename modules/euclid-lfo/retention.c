/* Current-bank SRAM journal. Header commits a complete bank; each record
 * subsequently commits independently so an interrupted edit cannot invalidate
 * other lanes. CRCs detect corruption, not cryptographic authenticity. */
#include "retention.h"
#ifdef EUL_SIDECAR_ONLY
/* On power-up stock omits its SRAM-restored bank from the disk-load mask.
 * Still load that bank's LFO sidecar; no battery-backed journal is read/written. */
volatile unsigned eul_nv_suspended=0,eul_nv_ready=0,eul_nv_pending=0;
unsigned eul_nv_bad_records=0;
void eul_nv_forget(void) { eul_nv_pending=0; }
void eul_nv_boot(unsigned bank) { eul_nv_pending=bank<16 ? bank+1 : 0; }
unsigned eul_nv_checkpoint(unsigned bank) { (void)bank; return 0; }
unsigned eul_nv_restore(unsigned bank) { (void)bank; return 0; }
void eul_nv_touch_part(unsigned bank,unsigned part) { (void)bank; (void)part; }
#else
#ifdef __m68k__
#define EUL_NV_DATA __attribute__((section(".data")))
#else
#define EUL_NV_DATA
#endif
#define EUL_NV_MAGIC 0x45554e31u
#define EUL_NV_RECORD 0x45555231u
volatile unsigned eul_nv_suspended=0,eul_nv_ready=0,eul_nv_pending=0;
static volatile unsigned eul_nv_ticket=0;
unsigned eul_nv_bad_records=0;
static EulBank eul_nv_stage EUL_NV_DATA={{{0}}};

static uint32_t nv_read(const volatile uint8_t *p) {
    return (uint32_t)p[0]<<24 | (uint32_t)p[1]<<16 | (uint32_t)p[2]<<8 | p[3];
}
static void nv_write(volatile uint8_t *p,uint32_t value) {
    p[0]=(uint8_t)(value>>24); p[1]=(uint8_t)(value>>16);
    p[2]=(uint8_t)(value>>8); p[3]=(uint8_t)value;
}
static unsigned nv_key(unsigned bank,uint32_t *key) {
    char path[260];
    if(!eul_io_path(path,bank,"work")) return 0;
    unsigned n=0; while(path[n]) ++n;
    *key=eul_crc32((const uint8_t *)path,n,0); return 1;
}
static uint16_t nv_crc(unsigned bank,unsigned index,const EulParams *p) {
    uint8_t identity[3]={(uint8_t)bank,(uint8_t)(index>>8),(uint8_t)index};
    return (uint16_t)eul_crc32((const uint8_t *)p,10,eul_crc32(identity,3,0));
}
/* Caller masks interrupts. Invalidation precedes all payload writes and
 * the commit marker's last byte is written last. No CRC work while masked. */
static void nv_record(volatile uint8_t *record,const EulParams *p,uint16_t crc) {
    nv_write(record,0);
    for(unsigned i=0;i<10;++i) record[4+i]=((const uint8_t *)p)[i];
    record[14]=(uint8_t)(crc>>8); record[15]=(uint8_t)crc;
    nv_write(record,EUL_NV_RECORD);
}
void eul_nv_forget(void) {
    uint16_t sr=eul_nv_lock();
    ++eul_nv_ticket; eul_nv_suspended=1; eul_nv_ready=0; eul_nv_pending=0;
    nv_write(eul_nv_memory(),0);
    eul_nv_unlock(sr);
}
void eul_nv_boot(unsigned bank) {
    eul_nv_ready=0; eul_nv_suspended=1;
    eul_nv_pending=bank<16 ? bank+1 : 0;
}
unsigned eul_nv_checkpoint(unsigned bank) {
    if(bank>=16 || !eul_nv_ready || eul_nv_suspended) return 0;
    volatile uint8_t *nv=eul_nv_memory();
    for(unsigned attempt=0;attempt<3;++attempt) {
        uint16_t sr=eul_nv_lock();
        unsigned ticket=++eul_nv_ticket,revision=eul_revision[bank];
        nv_write(nv,0);
        eul_nv_unlock(sr);
        uint32_t key;
        if(!nv_key(bank,&key)) return 0;
        for(unsigned index=0;index<EUL_PARTS*EUL_LANES;++index) {
            EulParams p;
            sr=eul_nv_lock();
            if(ticket!=eul_nv_ticket) { eul_nv_unlock(sr); return 0; }
            p=eul_bank[bank][index/EUL_LANES][index%EUL_LANES];
            eul_nv_unlock(sr);
            if(!eul_record_valid((const uint8_t *)&p)) return 0;
            uint16_t crc=nv_crc(bank,index,&p);
            sr=eul_nv_lock();
            if(ticket!=eul_nv_ticket) { eul_nv_unlock(sr); return 0; }
            nv_record(nv+16+16*index,&p,crc);
            eul_nv_unlock(sr);
        }
        uint8_t header[8];
        for(unsigned i=0;i<4;++i) {
            header[i]=(uint8_t)(key>>(24-8*i));
            header[i+4]=(uint8_t)(bank>>(24-8*i));
        }
        uint32_t crc=eul_crc32(header,8,0);
        sr=eul_nv_lock();
        if(ticket!=eul_nv_ticket) { eul_nv_unlock(sr); return 0; }
        if(revision==eul_revision[bank]) {
            nv_write(nv+4,key); nv_write(nv+8,bank); nv_write(nv+12,crc);
            nv_write(nv,EUL_NV_MAGIC);
            eul_nv_unlock(sr); return 1;
        }
        eul_nv_unlock(sr); /* Edit during checkpoint: retry with fresh data. */
    }
    return 0; /* Invalid header, so boot falls back to the validated sidecar. */
}
void eul_nv_touch_part(unsigned bank,unsigned part) {
    if(bank>=16 || bank!=eul_current_bank() || part>=EUL_PARTS || !eul_nv_ready || eul_nv_suspended) return;
    volatile uint8_t *nv=eul_nv_memory();
    uint32_t key;
    if(!nv_key(bank,&key)) return;
    /* Save-as/rename can change the project path without reloading the Part.
     * Re-key the complete current bank on its next edit, never retain edits
     * under the previous project's identity. Also repair an absent cache. */
    if(nv_read(nv)!=EUL_NV_MAGIC || nv_read(nv+4)!=key || nv_read(nv+8)!=bank) {
        eul_nv_checkpoint(bank); return;
    }
    for(unsigned lane=0;lane<EUL_LANES;++lane) {
        uint16_t sr=eul_nv_lock();
        if(nv_read(nv)!=EUL_NV_MAGIC || nv_read(nv+8)!=bank) {
            eul_nv_unlock(sr); return;
        }
        unsigned ticket=eul_nv_ticket,revision=eul_revision[bank];
        EulParams p=eul_bank[bank][part][lane];
        eul_nv_unlock(sr);
        if(!eul_record_valid((const uint8_t *)&p)) continue;
        unsigned index=part*EUL_LANES+lane;
        uint16_t crc=nv_crc(bank,index,&p);
        sr=eul_nv_lock();
        if(ticket==eul_nv_ticket && revision==eul_revision[bank] &&
           nv_read(nv)==EUL_NV_MAGIC && nv_read(nv+8)==bank)
            nv_record(nv+16+16*index,&p,crc);
        eul_nv_unlock(sr);
    }
}
unsigned eul_nv_restore(unsigned bank) {
    if(bank>=16 || eul_refused[bank]) return 0;
    volatile uint8_t *nv=eul_nv_memory();
    uint32_t key;
    if(!nv_key(bank,&key) || nv_read(nv)!=EUL_NV_MAGIC ||
       nv_read(nv+4)!=key || nv_read(nv+8)!=bank) return 0;
    uint8_t header[8];
    for(unsigned i=0;i<8;++i) header[i]=nv[4+i];
    if(nv_read(nv+12)!=eul_crc32(header,8,0) || !eul_snapshot(bank,eul_nv_stage)) return 0;
    unsigned changed=0;
    for(unsigned index=0;index<EUL_PARTS*EUL_LANES;++index) {
        volatile uint8_t *record=nv+16+16*index;
        EulParams p;
        for(unsigned i=0;i<10;++i) ((uint8_t *)&p)[i]=record[4+i];
        if(nv_read(record)!=EUL_NV_RECORD || !eul_record_valid((const uint8_t *)&p) ||
           nv_crc(bank,index,&p)!=((unsigned)record[14]<<8 | record[15])) {
            ++eul_nv_bad_records; continue;
        }
        EulParams *old=&eul_nv_stage[index/EUL_LANES][index%EUL_LANES];
        for(unsigned i=0;i<10;++i)
            if(((uint8_t *)old)[i]!=((uint8_t *)&p)[i]) changed=1;
        *old=p;
    }
    if(changed) { eul_publish(bank,eul_nv_stage); eul_dirty[bank]=1; }
    return 1;
}

#endif
