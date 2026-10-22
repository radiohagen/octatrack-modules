#ifndef EUCLID_LFO_LIFECYCLE_H
#define EUCLID_LFO_LIFECYCLE_H
#include "storage.h"

enum { EUL_IO_OK, EUL_IO_MISSING, EUL_IO_BAD, EUL_IO_ERROR };
extern EulBank eul_bank[16];
extern volatile unsigned eul_revision[16];
extern volatile uint8_t eul_refused[16], eul_backup[16], eul_dirty[16];
extern unsigned eul_io_errors;

/* Engine-task-only file adapter; no disk calls from the panel or waveform. */
unsigned eul_io_read(const char *path,uint8_t *file);
unsigned eul_io_write(const char *path,const uint8_t *file);
unsigned eul_io_copy(const char *dst,const char *src);
unsigned eul_io_path(char *out,unsigned bank,const char *suffix);
void eul_io_refuse(unsigned bank);
unsigned eul_current_bank(void);
void eul_publish(unsigned bank,const EulBank source);
void eul_publish_part(unsigned bank,unsigned part,const EulParams *source);
unsigned eul_snapshot(unsigned bank,EulBank dest);
unsigned eul_snapshot_part(unsigned bank,unsigned part,EulParams *dest);
void eul_finish_write(unsigned bank,unsigned revision);
void eul_schedule(unsigned bank);

void eul_load_mask(unsigned mask);
void eul_load_all(void);
void eul_new_project(void);
void eul_write_mask(unsigned mask);
void eul_answer(unsigned answer,unsigned bank);
void eul_bank_copy(const char *dst,const char *src);
void eul_part_save(unsigned part);
void eul_part_clear(unsigned part);
void eul_part_restore(unsigned bank,unsigned part);
#endif
