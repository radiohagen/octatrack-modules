/* SPDX-License-Identifier: MIT */
#include "engine.h"
#include "tables.h"

#if (-1 >> 1) != -1
#error Supersaw fixed-point arithmetic requires arithmetic signed right shift
#endif

static int32_t lookup(const int16_t *table, uint32_t phase) {
    /* A larger table makes each oscillator one bounded read. Round the
     * phase to the closest sample, wrapping naturally at the cycle edge. */
    return table[(phase + 0x100000u) >> 21];
}
void ss_init(struct ss_voice *voice) {
    for (unsigned i = 0; i < 7; ++i) voice->phase[i] = 0;
    voice->sub_phase = 0;
    voice->last = 0; voice->pending = 0;
    voice->base = voice->controls = voice->bank = 0;
    voice->centre_weight = voice->side_weight = voice->sub_gain = voice->drive_gain = 0;
    for (unsigned i = 0; i < 7; ++i) voice->increments[i] = 0;
}
static void ss_prepare(struct ss_voice *voice, const struct ss_params *params) {
    uint32_t base = params->increment;
    unsigned detune = params->detune & 127, mix = params->mix & 127;
    unsigned sub = params->sub & 127, drive = params->drive & 127;
    if (base < 1024) base = 1024;
    if (base > 0x7d000000u) base = 0x7d000000u;
    uint32_t controls = detune | (mix << 8) | (sub << 16) | (drive << 24);
    if (voice->base == base && voice->controls == controls) return;
    voice->base = base; voice->controls = controls;
    uint32_t maximum = 0;
    for (unsigned i = 0; i < 7; ++i) {
        /* Split the Q20 ratio around unity: bounded signed 32-bit products,
         * avoiding a ColdFire 64-bit runtime helper. At most one phase LSB
         * of rounding error, applied once per source call. */
        int32_t delta = (int32_t)ss_ratios[detune][i] - 1048576;
        int32_t offset = ((int32_t)(base >> 16) * delta
                       + (int32_t)(base & 65535) * delta / 65536) / 16;
        voice->increments[i] = (uint32_t)((int32_t)base + offset);
        if (voice->increments[i] > maximum) maximum = voice->increments[i];
    }
    unsigned bank = 0;
    while (bank < 7 && maximum <= (0x7fffffffu >> (bank + 1))) ++bank;
    voice->bank = bank;
    /* Constant weights: MIX 0 is the centre oscillator, MIX 127 makes
     * the six side oscillators together as loud as the centre. The sub
     * shares a fixed output budget. No per-sample variable division. */
    int32_t side_gain = (int32_t)mix * 129;
    int32_t centre_gain = 32768 - side_gain;
    int32_t sub_gain = (int32_t)sub * 64;
    int32_t saw_gain = 32768 - sub_gain;
    voice->drive_gain = 256 + (int32_t)drive * 6;
    voice->centre_weight = (centre_gain * saw_gain) >> 15;
    voice->side_weight = (((side_gain * 5461) >> 15) * saw_gain) >> 15;
    voice->sub_gain = sub_gain;
}
static void ss_core_render(struct ss_voice *voice, const struct ss_params *params,
               int16_t *output, uint32_t count) {
    ss_prepare(voice, params);
    uint32_t base = voice->base;
    const int16_t *table = ss_saws[voice->bank];
    int32_t centre_weight = voice->centre_weight, side_weight = voice->side_weight;
    int32_t sub_gain = voice->sub_gain, drive_gain = voice->drive_gain;
    unsigned drive = params->drive & 127;
    /* Keep one oscillator's phase, increment and weight in registers. The
     * bounded accumulator avoids spilling eight live oscillator lanes on
     * every sample. Phase continuity is independent of external call splitting. */
    while (count) {
        uint32_t block = count > 32 ? 32 : count;
        int32_t sum[32];
        for (uint32_t n = 0; n < block; ++n) sum[n] = 0;
        for (unsigned lane = 0; lane < 8; ++lane) {
            uint32_t phase = lane == 7 ? voice->sub_phase : voice->phase[lane];
            uint32_t step = lane == 7 ? base / 2 : voice->increments[lane];
            int32_t weight = lane == 7 ? sub_gain : lane == 3 ? centre_weight : side_weight;
            const int16_t *wave = lane == 7 ? ss_sine : table;
            if (weight) {
                for (uint32_t n = 0; n < block; ++n) {
                    sum[n] += lookup(wave, phase) * weight;
                    phase += step;
                }
            } else {
                phase += step * block;
            }
            if (lane == 7) voice->sub_phase = phase; else voice->phase[lane] = phase;
        }
        for (uint32_t n = 0; n < block; ++n) {
            int32_t sample = sum[n] >> 15;
            /* Symmetric bounded cubic drive. Zero bypasses it exactly. */
            if (drive) {
                int32_t x = (sample * drive_gain) >> 8;
                if (x > 32767) x = 32767;
                if (x < -32767) x = -32767;
                int32_t square = (x * x) >> 15;
                int32_t cube = (square * x) >> 15;
                sample = x - ((cube * 10923) >> 15);
            }
            output[n] = (int16_t)sample;
        }
        output += block;
        count -= block;
    }
}

/* Half-rate synthesis leaves headroom for the standard remix. Linear
 * interpolation has one output sample of latency. Pending preserves the
 * resampler across arbitrary native sub-frame call boundaries. */
void ss_render(struct ss_voice *voice, const struct ss_params *params,
               int16_t *output, uint32_t count) {
    struct ss_params core = *params;
    if (core.increment < 512) core.increment = 512;
    if (core.increment > 0x3e800000u) core.increment = 0x3e800000u;
    core.increment *= 2;
    if (voice->pending && count) {
        *output++ = voice->last;
        voice->pending = 0; --count;
    }
    while (count) {
        uint32_t block = count > 32 ? 16 : (count + 1) / 2;
        int16_t audio[16];
        ss_core_render(voice, &core, audio, block);
        for (uint32_t i = 0; i < block; ++i) {
            *output++ = (int16_t)(((int32_t)voice->last + audio[i]) >> 1);
            voice->last = audio[i]; --count;
            if (count) { *output++ = audio[i]; --count; }
            else voice->pending = 1;
        }
    }
}
