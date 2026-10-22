/* STORE client policy. Host tests use the same code with a fault-injecting
 * file adapter; native_io.c binds it to the firmware's engine-task I/O. */
#include "lifecycle.h"
#include "retention.h"
#ifdef __m68k__
#define EUL_DATA __attribute__((section(".data")))
#else
#define EUL_DATA
#endif

volatile unsigned eul_revision[16] EUL_DATA={0};
volatile uint8_t eul_refused[16] EUL_DATA={0};
volatile uint8_t eul_backup[16] EUL_DATA={0};
volatile uint8_t eul_dirty[16] EUL_DATA={0};
unsigned eul_io_errors=0;
static EulBank eul_stage EUL_DATA={{{0}}};
static uint8_t eul_file[EUL_FILE_BYTES] EUL_DATA={0};
static char eul_path[260] EUL_DATA={0};
static char eul_source[260] EUL_DATA={0};
static uint8_t eul_reload_failed[16] EUL_DATA={0};

static void empty_stage(void) {
    uint8_t *p=(uint8_t *)eul_stage;
    for (unsigned i=0;i<EUL_BANK_BYTES;++i) p[i]=0;
}
static void refuse(unsigned bank) {
    eul_refused[bank]=1;
    eul_io_refuse(bank);
}
static unsigned read_stage(const char *path) {
    unsigned result=eul_io_read(path,eul_file);
    if (result==EUL_IO_OK && !eul_file_decode(eul_stage,eul_file,EUL_FILE_BYTES))
        result=EUL_IO_BAD;
    if (result==EUL_IO_MISSING) empty_stage();
    return result;
}
void eul_load_mask(unsigned mask) {
    eul_nv_suspended=1;
    unsigned retained=eul_nv_pending;
    if(retained) mask|=1u<<(retained-1);
    for (unsigned b=0;b<16;++b) if (mask&(1u<<b)) {
        eul_refused[b]=0; eul_backup[b]=0; eul_dirty[b]=0;
        unsigned result=EUL_IO_ERROR;
        if(eul_reload_failed[b]) {
            /* Stock has already reloaded its bank. If its companion copy
             * failed, loading an older .work would silently mix two states. */
            eul_reload_failed[b]=0; result=EUL_IO_BAD;
        } else if (eul_io_path(eul_path,b,"work")) result=read_stage(eul_path);
        if (result!=EUL_IO_OK && result!=EUL_IO_MISSING) {
            /* Never play settings from the previous project/bank when this
             * load failed. Refusal also prevents a later save destroying it. */
            empty_stage(); refuse(b);
            if (result==EUL_IO_ERROR) ++eul_io_errors;
        }
        eul_publish(b,eul_stage);
    }
    if(retained) eul_nv_restore(retained-1);
    eul_nv_pending=0;
}
void eul_load_all(void) { eul_nv_forget(); eul_load_mask(0xffff); }
void eul_load_post(void) {
    eul_nv_ready=1; eul_nv_suspended=0;
    unsigned bank=eul_current_bank();
    if(bank<16) {
        eul_nv_checkpoint(bank);
        if(eul_dirty[bank]) eul_schedule(bank);
    }
}
void eul_new_project(void) {
    eul_nv_forget();
    empty_stage();
    for (unsigned b=0;b<16;++b) {
        eul_refused[b]=0; eul_backup[b]=0; eul_dirty[b]=1;
        eul_reload_failed[b]=0;
        eul_publish(b,eul_stage);
    }
    eul_nv_ready=1; eul_nv_suspended=0;
}
void eul_write_mask(unsigned mask) {
    for (unsigned b=0;b<16;++b) {
        if (eul_refused[b] || (!(mask&(1u<<b)) && !eul_dirty[b])) continue;
        unsigned revision=eul_revision[b];
        if (!eul_snapshot(b,eul_stage) ||
            !eul_file_encode(eul_file,EUL_FILE_BYTES,eul_stage) ||
            !eul_io_path(eul_path,b,"work")) {
            ++eul_io_errors; eul_dirty[b]=1; continue;
        }
        if (eul_backup[b]) {
            if (!eul_io_path(eul_source,b,"bak") ||
                eul_io_copy(eul_source,eul_path)!=EUL_IO_OK) {
                ++eul_io_errors; eul_dirty[b]=1; continue;
            }
            /* Preserve the original backup across a failed write/retry. */
            eul_backup[b]=0;
        }
        if (eul_io_write(eul_path,eul_file)!=EUL_IO_OK) {
            ++eul_io_errors; eul_dirty[b]=1; continue;
        }
        /* An edit while file I/O yielded must survive as pending work. */
        eul_finish_write(b,revision);
    }
}
void eul_answer(unsigned answer,unsigned bank) {
    if (bank>=16 || !eul_refused[bank] || answer<1 || answer>2) return;
    /* UI task: record policy only. No file I/O in this callback. */
    eul_backup[bank]=answer==2;
    eul_refused[bank]=0;
    eul_dirty[bank]=1;
    eul_schedule(bank);
}
/* Only a final /bank01..16.work or .strd component can be translated.
 * Directory names containing "bank" must never be changed. */
static unsigned sidecar_path(char *out,const char *in,unsigned *bank) {
    unsigned n=0,base=0;
    while (n<259 && in[n]) { out[n]=in[n]; if(in[n]=='/') base=n+1; ++n; }
    if (n==259 || !base || n-base!=11) return 0;
    out[n]=0;
    char *s=out+base;
    if (s[0]!='b'||s[1]!='a'||s[2]!='n'||s[3]!='k'||s[6]!='.') return 0;
    if(s[4]<'0'||s[4]>'1'||s[5]<'0'||s[5]>'9') return 0;
    unsigned number=(unsigned)(s[4]-'0')*10+(unsigned)(s[5]-'0');
    if(!number || number>16) return 0;
    if(!((s[7]=='w'&&s[8]=='o'&&s[9]=='r'&&s[10]=='k') ||
         (s[7]=='s'&&s[8]=='t'&&s[9]=='r'&&s[10]=='d'))) return 0;
    s[0]='e';s[1]='u';s[2]='l';s[3]='f'; *bank=number-1;
    return 1;
}
void eul_bank_copy(const char *dst,const char *src) {
    unsigned db,sb;
    if(!sidecar_path(eul_path,dst,&db) || !sidecar_path(eul_source,src,&sb)) return;
    /* A refused current work bank must not propagate into its stored copy. */
    unsigned n=0; while(src[n]) ++n;
    if(src[n-4]=='w' && eul_refused[sb]) return;
    unsigned length=0; while(dst[length]) ++length;
    unsigned reloading=dst[length-4]=='w';
    unsigned result=read_stage(eul_source);
    if(result!=EUL_IO_OK && result!=EUL_IO_MISSING) {
        if(reloading) eul_reload_failed[db]=1;
        refuse(db); ++eul_io_errors; return;
    }
    /* Missing legacy source means defaults, not a stale destination file.
     * Re-encode validated data rather than copying untrusted bytes blindly. */
    if(!eul_file_encode(eul_file,EUL_FILE_BYTES,eul_stage) ||
       eul_io_write(eul_path,eul_file)!=EUL_IO_OK) {
        if(reloading) eul_reload_failed[db]=1;
        ++eul_io_errors; eul_dirty[db]=1;
    } else if(reloading) {
        eul_reload_failed[db]=0;
    }
}
void eul_part_save(unsigned part) {
    unsigned bank=eul_current_bank();
    EulParams stage[EUL_LANES]; /* UI-local; never share the engine I/O staging. */
    if(bank>=16 || part>=4 || !eul_snapshot_part(bank,part,stage)) return;
    eul_publish_part(bank,part+4,stage); eul_dirty[bank]=1;
}
void eul_part_clear(unsigned part) {
    unsigned bank=eul_current_bank();
    if(bank>=16 || part>=4) return;
    EulParams stage[EUL_LANES];
    EulParams zero={0};
    for(unsigned lane=0;lane<EUL_LANES;++lane) stage[lane]=zero;
    eul_publish_part(bank,part,stage);
    eul_publish_part(bank,part+4,stage); eul_dirty[bank]=1;
}
void eul_part_restore(unsigned bank,unsigned part) {
    EulParams stage[EUL_LANES];
    if(bank>=16 || part>=4 || !eul_snapshot_part(bank,part+4,stage)) return;
    eul_publish_part(bank,part,stage); eul_dirty[bank]=1;
}
