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
    /* Runtime-only previous scaled phase. Read only while last_hit is valid;
     * edits, context changes and terminals invalidate that history first. */
    uint32_t position;
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
/* One logical edit increment = one value, after editor-only resistance.
 * Dependencies clamp immediately, and values never wrap at their limits.
 * Field 3 edits shape only; virtual field 10 edits DIR in mode bit 2. */
unsigned eul_edit(EulParams *p, unsigned field, int delta);
/* Native phase clock, scaled before native trigger/wrap/ONE/HALF handling.
 * MIDI uses the native tick increment; audio uses eul_audio_clock below.
 * Native increments fit signed 27 bits. Carry signed division residue so odd
 * lengths do not accumulate truncation drift, including reverse SPD. */
int32_t eul_clock(int32_t increment, unsigned steps, int32_t *remainder);
/* Exact audio-frame clock. Signed live SPD is Q8; tempo is BPM*24, MULT
 * is its native shift (0..6). Requires tempo<=8191 and steps=1..16.
 * Carry is in units of 1/(496125*steps); reset it when steps changes.
 * Only 32-bit arithmetic, including fractional/modulated and reverse SPD. */
int32_t eul_audio_clock(int speed, unsigned tempo, unsigned mult,
                        unsigned steps, int32_t *remainder);
/* Runtime-only exact-clock coefficients; never part of the saved payload.
 * Zero initialization is invalid (steps cannot be zero), forcing preparation.
 * Caller owns residue/context resets, exactly as for eul_audio_clock. */
typedef struct {
    int speed;
    unsigned tempo, mult, steps;
    int32_t result, quotient, fraction, denominator;
} EulAudioClock;
int32_t eul_audio_clock_cached(EulAudioClock *clock,int speed,unsigned tempo,
                              unsigned mult,unsigned steps,int32_t *remainder);
#endif
