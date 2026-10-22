#ifndef EUCLID_LFO_STORAGE_H
#define EUCLID_LFO_STORAGE_H
#include "engine.h"

#define EUL_PARTS 8u /* Four working Parts, followed by their saved copies. */
#define EUL_BANK_BYTES (EUL_PARTS * EUL_LANES * 10u)
#define EUL_FILE_BYTES (16u + EUL_BANK_BYTES)
typedef EulParams EulBank[EUL_PARTS][EUL_LANES];

/* Exact-size, endian-independent version 1 sidecar codec. No file I/O,
 * native project access, allocation or publication to the audio callback.
 * The caller supplies a separate staging bank, then publishes on success.
 * A bad or future file is refused, not normalized or partially loaded.
 * Input and output must not overlap. Failure leaves output untouched. */
unsigned eul_file_encode(uint8_t *out, unsigned size, const EulBank bank);
unsigned eul_file_decode(EulBank out, const uint8_t *file, unsigned size);
uint32_t eul_crc32(const uint8_t *p,unsigned size,uint32_t crc);
unsigned eul_record_valid(const uint8_t *p);
#endif
