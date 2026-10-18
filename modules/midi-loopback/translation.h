#ifndef LOOPBACK_TRANSLATION_H
#define LOOPBACK_TRANSLATION_H
#include <stdint.h>

enum { LT_CONTEXTS=64, LT_TRACKS=8, LT_FIELDS=4, LT_RECORD=5,
       LT_PART_BYTES=LT_TRACKS*LT_RECORD,
       LT_TABLE_BYTES=LT_CONTEXTS*LT_PART_BYTES,
       LT_PAYLOAD_BYTES=2*LT_TABLE_BYTES };
/* Record: RE-MAP, SOURCE REF, TARGET REF, symmetric RANGE, initialized=1.
 * Five zero bytes mean the disabled OT preset, so an absent file is safe. */
extern uint8_t lt_work[LT_TABLE_BYTES], lt_saved[LT_TABLE_BYTES];
extern uint32_t lt_readonly, lt_dirty, lt_storage_busy;
int lt_get(unsigned context, unsigned track, unsigned field);
int lt_set(unsigned context, unsigned track, unsigned field, unsigned value);
int lt_ui_get(unsigned track, unsigned field);
int lt_ui_set(unsigned track, unsigned field, unsigned value);
void lt_apply_format(char *buffer,unsigned value);
void lt_note_format(char *buffer,unsigned value);
void lt_number_format(char *buffer,unsigned value);
void lt_range_format(char *buffer,unsigned value);
int lt_map(int note, unsigned source, unsigned target, unsigned radius);
int lt_valid(const uint8_t *payload, unsigned length);
void lt_reset(void);
void lt_flush_all(void);
void lt_part_copy(unsigned destination, unsigned source, unsigned length);
void lt_part_init(unsigned destination);
void lt_load_banks(unsigned mask);
int lt_save_banks(unsigned mask);
int lt_copy_guard(const char *source);
int lt_copy_done(const char *destination, const char *source);
void lt_new_project(void);
void lt_answer(unsigned answer, unsigned bank);
void lt_path(unsigned bank, char *buffer);
int lt_fopen(const char *path, const char *mode, void *context);
int lt_fread(void *context, void *buffer, unsigned length);
int lt_fwrite(void *context, const void *buffer, unsigned length);
int lt_fclose(void *context);
int lt_fsize(void *context);
int lt_exists(const char *path);
int lt_fcopy(const char *destination, const char *source, unsigned zero);
uint32_t lt_crc(const void *buffer, unsigned length);
void lt_refuse(unsigned bank);
void lt_mark_dirty(unsigned context);
/* prepare/commit/release/duplicate use the unchanged source ownership index.
 * Result: destination flags | internal pitch << 8 | external pitch << 16. */
uint32_t lt_prepare(unsigned index, unsigned track, unsigned destinations, unsigned ui);
uint32_t lt_commit(unsigned index, unsigned destinations);
uint32_t lt_release(unsigned index, unsigned destinations);
uint32_t lt_duplicate(unsigned index, unsigned destinations);
/* Small assembly adapters. No I/O or allocation on the note path. */
void lb_flush(unsigned track);
int lt_play_context(unsigned track);
int lt_ui_context(void);
uint16_t lt_lock(void);
void lt_unlock(uint16_t sr);
#endif
