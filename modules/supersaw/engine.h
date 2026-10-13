/* SPDX-License-Identifier: MIT
 * Original fixed-point seven-saw engine. No OP-1 code or firmware tables.
 * One note per instance; the caller owns its amplitude envelope.
 */
#ifndef OCTABAM_SUPERSAW_H
#define OCTABAM_SUPERSAW_H
#include <stdint.h>
struct ss_voice {
    uint32_t phase[7], sub_phase;
    int16_t last; uint16_t pending;
    /* Derived controls are constant until pitch or a knob changes. */
    uint32_t base, increments[7], controls, bank;
    int32_t centre_weight, side_weight, sub_gain, drive_gain;
};
struct ss_params { uint32_t increment; uint8_t detune, mix, sub, drive; };
void ss_init(struct ss_voice *voice);
void ss_render(struct ss_voice *voice, const struct ss_params *params,
               int16_t *output, uint32_t count);
#endif
