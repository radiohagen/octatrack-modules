#ifndef EUCLID_LFO_ENGINE_H
#define EUCLID_LFO_ENGINE_H
#include <stdint.h>

#define EUL_PHASE 0x800000u
#define EUL_LEVEL 32768u
#define EUL_STEPS 16u
#define EUL_LANES 48u

enum { EUL_ENV, EUL_GATE, EUL_RAND, EUL_LOOP };
enum { EUL_SHAPE_MASK=3, EUL_NEGATIVE=4, EUL_DIRECTION_FIELD=10 };
/* Byte-only, endian-independent payload. Changes require a file version bump.
 * Zero STEPS is an absent record, interpreted as the default, never written
 * back by the audio/MIDI callback. */
typedef struct {
    uint8_t steps, pulses, rotate, mode, attack, decay; /* mode: shape bits 0–1, NEG bit 2 */
    uint8_t accents, accent_rotate, boost, swing;
} EulParams;

typedef struct {
    EulParams params, source;
    uint16_t hits, accents;
    uint8_t previous[EUL_STEPS];
    uint16_t boundaries[EUL_STEPS];
    uint16_t values[EUL_STEPS];
    uint32_t attack, decay, length, edge;
    uint32_t rng, phase, origin, target, level;
    uint8_t ready, last_hit, last_step, reserved;
} EulState;

void eul_defaults(EulParams *p);
void eul_normalize(EulParams *p);
void eul_masks(const EulParams *p, uint16_t *hits, uint16_t *accents);
/* Output is Q23, positive or negative by DIR, at most 2x native full scale
 * with accent boost. Native unsigned DEP supplies amount; native clamps apply.
 * `reset` is the native LFO retrigger, not the transport state: FREE runs
 * while stopped. `terminal` is supplied for native ONE/HALF endpoints. */
int32_t eul_process(EulState *s, const EulParams *p, uint32_t phase,
                    unsigned reset, unsigned terminal, unsigned identity);
/* One raw encoder count = one increment, no velocity or push acceleration.
 * Dependencies clamp immediately, and values never wrap at their limits.
 * Field 3 edits shape only; virtual field 10 edits DIR in mode bit 2. */
unsigned eul_edit(EulParams *p, unsigned field, int delta);
/* Native phase clock, scaled before native trigger/wrap/ONE/HALF handling.
 * 16 steps preserve the stock cycle; one step is always 1/16 of that cycle.
 * Native increments fit signed 27 bits. Carry signed division residue so odd
 * lengths do not accumulate truncation drift, including reverse SPD. */
int32_t eul_clock(int32_t increment, unsigned steps, int32_t *remainder);
#endif
