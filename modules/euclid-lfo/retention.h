#ifndef EUCLID_LFO_RETENTION_H
#define EUCLID_LFO_RETENTION_H
#include "lifecycle.h"
#define EUL_NV_BASE 0x100fa5e0u
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
void eul_load_post(void);
#endif
