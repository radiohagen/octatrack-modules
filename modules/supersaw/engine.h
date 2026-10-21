/* SPDX-License-Identifier: MIT
 * Original fixed-point two-saw engine. No OP-1 code or firmware tables.
 * One note per instance; the caller owns its amplitude envelope.
 */
#ifndef OCTABAM_SUPERSAW_H
#define OCTABAM_SUPERSAW_H
#include <stdint.h>
struct ss_voice {
    uint32_t phase[2], sub_phase;
    /* Three source samples for the causal four-point interpolator. */
    int16_t last, previous, older; uint16_t pending;
    /* Derived controls are constant until pitch or a knob changes. */
    uint32_t base, increments[2], controls, bank;
    int32_t saw_weight, morph_weight, sub_gain, drive_gain;
};
struct ss_params { uint32_t increment; uint8_t detune, morph, sub, drive; };
void ss_init(struct ss_voice *voice);
void ss_render(struct ss_voice *voice, const struct ss_params *params,
               int16_t *output, uint32_t count);
#endif
