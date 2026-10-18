/* STORE client, following the existing bank-companion lifecycle pattern.
 * lbnt01..16.work/strd: 16-byte BE header, then working and saved Parts.
 * No native bank bytes, sample metadata or retained SRAM are repurposed. */
#include "translation.h"
#define DATA __attribute__((section(".data")))
enum { BANK_BYTES=4*LT_PART_BYTES, PAYLOAD=2*BANK_BYTES, FILE_BYTES=16+PAYLOAD };
static uint8_t context[4120] DATA={0}, image[FILE_BYTES] DATA={0};
static char path[260] DATA={0}, source_path[260] DATA={0};
static uint32_t present DATA=0, failed DATA=0, backup DATA=0;

static uint32_t get32(const uint8_t *p) {
    return (uint32_t)p[0]<<24 | (uint32_t)p[1]<<16 | (uint32_t)p[2]<<8 | p[3];
}
static void put32(uint8_t *p,uint32_t v) {
    p[0]=(uint8_t)(v>>24);p[1]=(uint8_t)(v>>16);p[2]=(uint8_t)(v>>8);p[3]=(uint8_t)v;
}
static void header(void) {
    put32(image,0x4c424e54u); /* LBNT */
    put32(image+4,1);
    put32(image+8,PAYLOAD);
    put32(image+12,lt_crc(image+16,PAYLOAD));
}
static int read_file(const char *name) {
    int exists=lt_exists(name);
    if (!exists) return 0;
    if (exists<0 || lt_fopen(name,"r",context)<0) return -7;
    int ok=lt_fsize(context)==FILE_BYTES && lt_fread(context,image,FILE_BYTES)==1;
    if (lt_fclose(context)<0) ok=0;
    if (!ok || get32(image)!=0x4c424e54u || get32(image+4)!=1 ||
        get32(image+8)!=PAYLOAD || get32(image+12)!=lt_crc(image+16,PAYLOAD) ||
        !lt_valid(image+16,PAYLOAD)) return -7;
    return 1;
}
static int write_file(const char *name) {
    header();
    if (lt_fopen(name,"w",context)<0) return -7;
    int ok=lt_fwrite(context,image,FILE_BYTES)==1;
    if (lt_fclose(context)<0) ok=0;
    return ok ? 0 : -7;
}
static void empty_image(void) {
    for (unsigned i=16;i<FILE_BYTES;++i) image[i]=0;
}
void lt_load_banks(unsigned mask) {
    lt_storage_busy=1;
    for (unsigned bank=0;bank<16;++bank) if (mask&(1u<<bank)) {
        unsigned bit=1u<<bank;
        lt_path(bank,path);
        int result=read_file(path);
        if (result<=0) empty_image();
        uint16_t sr=lt_lock();
        /* Flush translated outgoing identities before atomic publication.
         * OFF-only native ownership remains exactly with Loopback. */
        lt_flush_all();
        for (unsigned i=0;i<BANK_BYTES;++i) {
            lt_work[bank*BANK_BYTES+i]=image[16+i];
            lt_saved[bank*BANK_BYTES+i]=image[16+BANK_BYTES+i];
        }
        lt_dirty&=~bit;
        lt_readonly&=~bit;
        failed&=~bit;
        backup&=~bit;
        present=(present&~bit)|(result ? bit : 0);
        if (result<0) lt_readonly|=bit;
        lt_unlock(sr);
        if (result<0) lt_refuse(bank);
    }
    lt_storage_busy=0;
}
int lt_save_banks(unsigned mask) {
    lt_storage_busy=1;
    for (unsigned bank=0;bank<16;++bank) if (mask&(1u<<bank)) {
        unsigned bit=1u<<bank;
        if (lt_readonly&bit) { lt_storage_busy=0;return -7; }
        lt_path(bank,path);
        if (backup&bit) {
            unsigned i=0;
            do { source_path[i]=path[i]; } while (path[i++]);
            /* The existing STORE BACKUP action is explicit user approval. */
            source_path[i-5]='b';source_path[i-4]='a';source_path[i-3]='k';source_path[i-2]=0;
            if (lt_fcopy(source_path,path,0)<0) {
                failed|=bit;lt_storage_busy=0;return -7;
            }
            backup&=~bit;
        }
        unsigned nonzero=0;
        for (unsigned i=0;i<BANK_BYTES;++i) {
            image[16+i]=lt_work[bank*BANK_BYTES+i];
            image[16+BANK_BYTES+i]=lt_saved[bank*BANK_BYTES+i];
            nonzero|=image[16+i]|image[16+BANK_BYTES+i];
        }
        /* An untouched project gets no new companion. Once present, even
         * clearing every setting must write an explicit empty payload. */
        if (!nonzero && !(present&bit)) { lt_dirty&=~bit;continue; }
        if (write_file(path)<0) { failed|=bit;lt_storage_busy=0;return -7; }
        present|=bit;failed&=~bit;lt_dirty&=~bit;
    }
    lt_storage_busy=0;
    return 0;
}
/* Native bank filename adapter, same contract as Harmony/PLOCKS companions.
 * Only exact bank01..16.work/strd basenames; no native file-format parser. */
static int companion(const char *native,char *out,unsigned *stored) {
    unsigned length=0,base=0;
    while (native[length] && length<259) {
        out[length]=native[length];
        if (native[length]=='/') base=length+1;
        ++length;
    }
    if (length==259 || length-base!=11) return -1;
    out[length]=0;
    const char *p=native+base;
    if (p[0]!='b'||p[1]!='a'||p[2]!='n'||p[3]!='k'||p[6]!='.'||
        p[4]<'0'||p[4]>'1'||p[5]<'0'||p[5]>'9') return -1;
    unsigned bank=(unsigned)(p[4]-'0')*10+(unsigned)(p[5]-'0');
    if (!bank || bank>16) return -1;
    if (p[7]=='w'&&p[8]=='o'&&p[9]=='r'&&p[10]=='k') *stored=0;
    else if (p[7]=='s'&&p[8]=='t'&&p[9]=='r'&&p[10]=='d') *stored=1;
    else return -1;
    out[base]='l';out[base+1]='b';out[base+2]='n';out[base+3]='t';
    return (int)bank-1;
}
int lt_copy_guard(const char *source) {
    unsigned stored=0;
    int bank=companion(source,source_path,&stored);
    return bank>=0 && !stored && ((lt_readonly|failed)&(1u<<bank)) ? -7 : 0;
}
int lt_copy_done(const char *destination,const char *source) {
    unsigned stored;
    if (companion(source,source_path,&stored)<0 || companion(destination,path,&stored)<0) return 0;
    int exists=lt_exists(source_path);
    if (exists<0) return -7;
    if (exists) return lt_fcopy(path,source_path,0)<0 ? -7 : 0;
    /* Missing source must replace a stale destination with OFF, not revive it. */
    if (!lt_exists(path)) return 0;
    empty_image();
    return write_file(path);
}
void lt_new_project(void) {
    lt_storage_busy=1;
    lt_reset();
    present=failed=backup=0;
    lt_storage_busy=0;
}
void lt_answer(unsigned answer,unsigned bank) {
    if (bank>=16 || !answer || answer>2) return;
    unsigned bit=1u<<bank;
    if (answer==2) backup|=bit;
    lt_readonly&=~bit;
    lt_dirty|=bit;
}
