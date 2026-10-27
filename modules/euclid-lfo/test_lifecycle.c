#include "lifecycle.h"
#include "retention.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

EulBank eul_bank[16];
static EulBank fixture,actual,empty;
static struct { char path[260]; uint8_t data[EUL_FILE_BYTES]; unsigned size; } files[64];
static unsigned count,current,refusals,schedules,reads,writes,copies;
static unsigned fail_read,fail_write,fail_copy,fail_snapshot,edit_during_write;
static unsigned other_project;
static uint8_t retained_memory[EUL_NV_BYTES];
volatile uint8_t *eul_nv_memory(void) { return retained_memory; }
uint16_t eul_nv_lock(void) { return 0; }
void eul_nv_unlock(uint16_t saved) { (void)saved; }

static unsigned find_file(const char *path,unsigned create) {
    for(unsigned i=0;i<count;++i) if(!strcmp(path,files[i].path)) return i;
    if(!create) return 64;
    assert(count<64); strcpy(files[count].path,path); return count++;
}
unsigned eul_io_read(const char *path,uint8_t *file) {
    ++reads;
    if(fail_read) return EUL_IO_ERROR;
    unsigned i=find_file(path,0);
    if(i==64) return EUL_IO_MISSING;
    if(files[i].size!=EUL_FILE_BYTES) return EUL_IO_BAD;
    memcpy(file,files[i].data,EUL_FILE_BYTES); return EUL_IO_OK;
}
unsigned eul_io_write(const char *path,const uint8_t *file) {
    ++writes;
    if(fail_write) return EUL_IO_ERROR;
    unsigned i=find_file(path,1);
    memcpy(files[i].data,file,EUL_FILE_BYTES); files[i].size=EUL_FILE_BYTES;
    if(edit_during_write) {
        eul_bank[0][0][0].pulses=7;
        ++eul_revision[0]; eul_dirty[0]=1; edit_during_write=0;
    }
    return EUL_IO_OK;
}
unsigned eul_io_copy(const char *dst,const char *src) {
    ++copies;
    if(fail_copy) return EUL_IO_ERROR;
    unsigned s=find_file(src,0); if(s==64) return EUL_IO_ERROR;
    unsigned d=find_file(dst,1);
    memcpy(files[d].data,files[s].data,EUL_FILE_BYTES); files[d].size=files[s].size;
    return EUL_IO_OK;
}
unsigned eul_io_path(char *out,unsigned bank,const char *suffix) {
    assert(bank<16); snprintf(out,260,"/SET/%s/eulf%02u.%s",other_project?"OTHER":"PROJECT",bank+1,suffix); return 1;
}
void eul_io_refuse(unsigned bank) { assert(bank<16); ++refusals; }
unsigned eul_current_bank(void) { return current; }
void eul_publish(unsigned bank,const EulBank source) {
    memcpy(eul_bank[bank],source,EUL_BANK_BYTES); ++eul_revision[bank];
}
void eul_publish_part(unsigned bank,unsigned part,const EulParams *source) {
    memcpy(eul_bank[bank][part],source,480); ++eul_revision[bank];
}
unsigned eul_snapshot(unsigned bank,EulBank dest) {
    if(fail_snapshot) return 0;
    memcpy(dest,eul_bank[bank],EUL_BANK_BYTES); return 1;
}
unsigned eul_snapshot_part(unsigned bank,unsigned part,EulParams *dest) {
    if(fail_snapshot) return 0;
    memcpy(dest,eul_bank[bank][part],480); return 1;
}
void eul_finish_write(unsigned bank,unsigned revision) {
    eul_dirty[bank]=eul_revision[bank]!=revision;
}
void eul_schedule(unsigned bank) { assert(bank<16); ++schedules; }
static void fresh(void) {
    eul_new_project();
    for(unsigned b=0;b<16;++b) eul_dirty[b]=0;
    count=current=refusals=schedules=reads=writes=copies=0;
    fail_read=fail_write=fail_copy=fail_snapshot=edit_during_write=0;
    other_project=0;
    eul_io_errors=0;
}
static void install(const char *path,const EulBank bank) {
    unsigned i=find_file(path,1);
    assert(eul_file_encode(files[i].data,EUL_FILE_BYTES,bank)); files[i].size=EUL_FILE_BYTES;
}
static void check_file(const char *path,const EulBank bank) {
    unsigned i=find_file(path,0); assert(i<64);
    assert(eul_file_decode(actual,files[i].data,files[i].size));
    assert(!memcmp(actual,bank,EUL_BANK_BYTES));
}
int main(void) {
    for(unsigned p=0;p<8;++p) for(unsigned l=0;l<48;++l) {
        eul_defaults(&fixture[p][l]); fixture[p][l].rotate=(uint8_t)((p+l)%8);
    }
    const char *work="/SET/PROJECT/eulf01.work",*stored="/SET/PROJECT/eulf01.strd";
    fresh(); install(work,fixture);
    memset(eul_bank,0xa5,sizeof(eul_bank));
    eul_load_all();
    assert(!memcmp(eul_bank[0],fixture,EUL_BANK_BYTES));
    for(unsigned b=1;b<16;++b) assert(!memcmp(eul_bank[b],empty,EUL_BANK_BYTES));
    assert(!refusals && reads==16 && !writes);
    puts("PASS: all-bank load installs all lanes/Parts, missing legacy files default without writes");

    memcpy(eul_bank[2],fixture,EUL_BANK_BYTES);
    memset(eul_bank[0],0,sizeof(EulBank)); eul_load_mask(1);
    assert(!memcmp(eul_bank[0],fixture,EUL_BANK_BYTES));
    assert(!memcmp(eul_bank[2],fixture,EUL_BANK_BYTES));
    eul_bank[0][1][47].pulses=6;
    eul_part_save(1);
    assert(eul_bank[0][5][47].pulses==6 && eul_bank[0][1][47].pulses==6);
    eul_bank[0][1][47].pulses=1;
    eul_part_restore(0,1);
    assert(eul_bank[0][1][47].pulses==6);
    eul_part_clear(1);
    assert(!memcmp(eul_bank[0][1],empty[0],480));
    assert(!memcmp(eul_bank[0][5],empty[0],480));
    assert(!memcmp(eul_bank[0][0],fixture[0],480));
    assert(!memcmp(eul_bank[2],fixture,EUL_BANK_BYTES));
    eul_part_save(4); eul_part_clear(99); current=16; eul_part_clear(0);
    puts("PASS: masked load, Part Save/Clear and invalid indices preserve unrelated banks and Parts");

    fresh(); install(work,fixture); unsigned bad=find_file(work,0);
    files[bad].data[4]=1; /* Unsupported version, also stale CRC. */
    uint8_t original[EUL_FILE_BYTES]; memcpy(original,files[bad].data,EUL_FILE_BYTES);
    eul_load_mask(1); assert(eul_refused[0] && refusals==1);
    assert(!memcmp(eul_bank[0],empty,EUL_BANK_BYTES));
    eul_answer(0,0); eul_write_mask(1); assert(!writes && eul_refused[0]);
    eul_answer(2,0); assert(eul_backup[0] && !eul_refused[0] && schedules==1);
    fail_copy=1; eul_write_mask(1);
    assert(!writes && eul_backup[0] && eul_dirty[0]);
    assert(!memcmp(files[bad].data,original,EUL_FILE_BYTES));
    fail_copy=0; fail_write=1; eul_write_mask(1);
    assert(!eul_backup[0] && eul_dirty[0] && copies==2);
    unsigned backup=find_file("/SET/PROJECT/eulf01.bak",0); assert(backup<64);
    assert(!memcmp(files[backup].data,original,EUL_FILE_BYTES));
    fail_write=0; eul_write_mask(1);
    assert(!eul_dirty[0] && copies==2);
    assert(!memcmp(files[backup].data,original,EUL_FILE_BYTES)); check_file(work,empty);
    puts("PASS: refusal/IGNORE and BACKUP failure/retry preserve original data and never replace backup on write retry");

    fresh(); install(work,fixture); fail_read=1; eul_load_mask(1);
    assert(eul_refused[0] && eul_io_errors==1); eul_write_mask(1); assert(!writes);
    fail_read=0; eul_load_mask(1); assert(!eul_refused[0]);
    fail_snapshot=1; eul_write_mask(1); assert(!writes && eul_dirty[0]);
    fail_snapshot=0; edit_during_write=1; eul_write_mask(1);
    check_file(work,fixture); assert(eul_dirty[0]);
    eul_write_mask(0); assert(!eul_dirty[0]); check_file(work,eul_bank[0]);
    puts("PASS: I/O and snapshot failures stay pending; edit during save is retained for the next write");

    fresh(); install(work,fixture);
    eul_bank_copy("/SET/PROJECT/bank01.strd","/SET/PROJECT/bank01.work"); check_file(stored,fixture);
    eul_bank_copy("/SET/PROJECT/bank01.work","/LEGACY/bank01.strd"); check_file(work,empty);
    unsigned before=writes;
    eul_bank_copy("/SET/bank-folder/other.work","/SET/PROJECT/bank01.work");
    eul_bank_copy("/SET/PROJECT/bank00.work","/SET/PROJECT/bank01.work");
    eul_bank_copy("/SET/PROJECT/bank17.work","/SET/PROJECT/bank01.work");
    eul_bank_copy("/SET/PROJECT/bank01.work.bak","/SET/PROJECT/bank01.work");
    assert(writes==before);
    files[find_file(stored,0)].size=0;
    install(work,fixture); /* Old .work must not masquerade as a successful reload. */
    eul_bank_copy("/SET/PROJECT/bank01.work","/SET/PROJECT/bank01.strd");
    assert(writes==before && eul_refused[0]); check_file(work,fixture);
    eul_load_mask(1);
    assert(eul_refused[0] && !memcmp(eul_bank[0],empty,EUL_BANK_BYTES));
    check_file(work,fixture);
    eul_new_project();
    for(unsigned b=0;b<16;++b) {
        assert(!memcmp(eul_bank[b],empty,EUL_BANK_BYTES));
        assert(!eul_refused[b] && !eul_backup[b] && eul_dirty[b]);
    }
    puts("PASS: bank store/reload, missing-source defaults, strict path scope, corrupt-copy refusal and new project");
    fresh(); install(work,fixture); eul_load_all(); eul_load_post();
#ifdef EUL_SIDECAR_ONLY
    memset(retained_memory,0xa5,sizeof(retained_memory));
    eul_bank[0][0][0].pulses=7; ++eul_revision[0]; eul_dirty[0]=1;
    eul_nv_touch_part(0,0);
    assert(!eul_nv_checkpoint(0));
    eul_nv_boot(0); eul_load_mask(0xfffe); eul_load_post();
    assert(!memcmp(eul_bank[0],fixture,EUL_BANK_BYTES));
    eul_bank[0][0][0].pulses=7; ++eul_revision[0]; eul_dirty[0]=1;
    eul_write_mask(1);
    EulBank saved; memcpy(saved,eul_bank[0],EUL_BANK_BYTES);
    memset(eul_bank,0,sizeof(eul_bank));
    eul_nv_boot(0); eul_load_mask(0xfffe); eul_load_post();
    assert(!memcmp(eul_bank[0],saved,EUL_BANK_BYTES));
    for(unsigned i=0;i<sizeof(retained_memory);++i) assert(retained_memory[i]==0xa5);
    puts("PASS: sidecar power-up loads the native retained bank; saved edits persist, unsaved edits revert, SRAM unchanged");
#else
    uint8_t journal_before[EUL_NV_BYTES];
    for(unsigned part=0;part<EUL_PARTS;++part) for(unsigned lane=0;lane<EUL_LANES;++lane) {
        memcpy(journal_before,retained_memory,sizeof(journal_before));
        eul_bank[0][part][lane].boost^=1; ++eul_revision[0];
        eul_nv_touch_lane(0,part,lane);
        unsigned begin=16+16*(part*EUL_LANES+lane),end=begin+16;
        assert(!memcmp(journal_before,retained_memory,begin));
        assert(!memcmp(journal_before+end,retained_memory+end,EUL_NV_BYTES-end));
        assert(memcmp(journal_before+begin,retained_memory+begin,16));
        EulParams saved=eul_bank[0][part][lane];
        eul_bank[0][part][lane].boost^=1;
        assert(eul_nv_restore(0));
        assert(!memcmp(&eul_bank[0][part][lane],&saved,sizeof(saved)));
    }
    memcpy(journal_before,retained_memory,sizeof(journal_before));
    eul_nv_touch_lane(0,0,48); eul_nv_touch_lane(16,0,0); eul_nv_touch_lane(0,8,0);
    eul_nv_touch_lane(1,0,0);
    assert(!memcmp(journal_before,retained_memory,sizeof(journal_before)));
    puts("PASS: single-lane retention updates only its record, all 384 working/saved audio/MIDI lanes recover; invalid contexts inert");
    fresh(); install(work,fixture); eul_load_all(); eul_load_post();
    assert(eul_nv_checkpoint(0));
    /* Edits in both audio/MIDI and working/saved copies, without a disk save. */
    eul_bank[0][0][0].pulses=7;
    eul_bank[0][3][47].boost=127;
    eul_bank[0][7][24].swing=29;
    ++eul_revision[0];
    eul_nv_touch_part(0,0); eul_nv_touch_part(0,3); eul_nv_touch_part(0,7);
    EulBank unsaved; memcpy(unsaved,eul_bank[0],EUL_BANK_BYTES);
    memset(eul_bank,0,sizeof(eul_bank));
    eul_nv_boot(0); eul_load_mask(0xfffe); eul_load_post();
    assert(!memcmp(eul_bank[0],unsaved,EUL_BANK_BYTES));
    check_file(work,fixture); assert(eul_dirty[0]);
    /* One torn/corrupted record falls back to the file; other edits survive. */
    retained_memory[16+4]^=1;
    memset(eul_bank,0,sizeof(eul_bank));
    eul_nv_boot(0); eul_load_mask(0xfffe);
    unsaved[0][0]=fixture[0][0];
    assert(!memcmp(eul_bank[0],unsaved,EUL_BANK_BYTES));
    assert(eul_nv_bad_records==1);
    /* Wrong bank/header cannot overlay another bank's current settings. */
    eul_nv_boot(1); eul_load_mask(0xfffd);
    assert(!memcmp(eul_bank[1],empty,EUL_BANK_BYTES));
    eul_nv_forget(); eul_nv_boot(0); eul_load_mask(0xfffe);
    assert(!memcmp(eul_bank[0],fixture,EUL_BANK_BYTES));
    puts("PASS: unsaved audio/MIDI and saved-Part SRAM recovery, per-record corruption fallback, wrong-bank and missing-cache fallback");
    eul_load_post();
    other_project=1;
    assert(!eul_nv_restore(0));
    eul_bank[0][0][0].pulses=7; ++eul_revision[0]; eul_nv_touch_lane(0,0,0);
    memcpy(eul_bank[0],fixture,EUL_BANK_BYTES);
    assert(eul_nv_restore(0) && eul_bank[0][0][0].pulses==7);
    other_project=0;
    assert(!eul_nv_restore(0));
    puts("PASS: project identity rejects foreign retained state and re-keys on the first edit after save-as/rename");
#endif
    return 0;
}
