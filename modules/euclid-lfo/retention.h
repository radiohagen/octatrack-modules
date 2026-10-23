#ifndef EUCLID_LFO_RETENTION_H
#define EUCLID_LFO_RETENTION_H
#include "lifecycle.h"
#define EUL_NV_BASE 0x100f8600u
#define EUL_NV_BYTES (16u + 16u * EUL_PARTS * EUL_LANES)
extern volatile unsigned eul_nv_suspended,eul_nv_ready,eul_nv_pending;
extern unsigned eul_nv_bad_records;
volatile uint8_t *eul_nv_memory(void);
uint16_t eul_nv_lock(void);
void eul_nv_unlock(uint16_t saved);
void eul_nv_forget(void);
void eul_nv_boot(unsigned bank);
unsigned eul_nv_checkpoint(unsigned bank);
unsigned eul_nv_restore(unsigned bank);
void eul_nv_touch_part(unsigned bank,unsigned part);
/* UI edits touch one record; Part lifecycle operations still touch all lanes.
 * Both paths retain save-as re-keying and ticket/revision commit guards. */
void eul_nv_touch_lane(unsigned bank,unsigned part,unsigned lane);
void eul_load_post(void);
#endif
