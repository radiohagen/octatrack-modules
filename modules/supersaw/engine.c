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
    for (unsigned i = 0; i < 2; ++i) voice->phase[i] = 0;
    /* A quarter-cycle offset makes subtraction a pulse at zero detune. */
    voice->phase[1] = 0x40000000u;
    voice->sub_phase = 0;
    voice->last = voice->previous = voice->older = 0; voice->pending = 0;
    voice->base = voice->controls = voice->bank = 0;
    voice->saw_weight = voice->morph_weight = voice->sub_gain = voice->drive_gain = 0;
    for (unsigned i = 0; i < 2; ++i) voice->increments[i] = 0;
}
/* Keep the cache guard before its arithmetic. Inlining lets GCC hoist
 * control products into every source call, even on a warm cache. */
static __attribute__((noinline)) void ss_prepare(struct ss_voice *voice, const struct ss_params *params) {
    uint32_t base = params->increment;
    unsigned detune = params->detune & 127, morph = params->morph & 127;
    unsigned sub = params->sub & 127, drive = params->drive & 127;
    if (base < 1024) base = 1024;
    if (base > 0x7d000000u) base = 0x7d000000u;
    uint32_t controls = detune | (morph << 8) | (sub << 16) | (drive << 24);
    if (voice->base == base && voice->controls == controls) return;
    voice->base = base; voice->controls = controls;
    uint32_t maximum = 0;
    for (unsigned i = 0; i < 2; ++i) {
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
    /* Equal saw pair. MORF continuously reverses the second saw's polarity:
     * sum at 0, difference (pulse at zero detune) at 127. Weights stay
     * bounded even at the endpoints, with a separate fixed sub budget. */
    int32_t sub_gain = (int32_t)sub * 64;
    int32_t saw_gain = 32768 - sub_gain;
    int32_t polarity = 32768 - (int32_t)morph * 65536 / 127;
    voice->drive_gain = 256 + (int32_t)drive * 6;
    voice->saw_weight = saw_gain / 2;
    voice->morph_weight = (voice->saw_weight * polarity) >> 15;
    voice->sub_gain = sub_gain;
}
static void ss_core_render(struct ss_voice *voice, const struct ss_params *params,
               int16_t *output, uint32_t output_count) {
    /* ss_render bounds each chunk to 32 output / 16 source samples. */
    uint32_t count = (output_count + 1) / 2;
    uint32_t pairs = output_count / 2;
    ss_prepare(voice, params);
    uint32_t base = voice->base;
    const int16_t *table = ss_saws[voice->bank];
    int32_t saw_weight = voice->saw_weight, morph_weight = voice->morph_weight;
    int32_t sub_gain = voice->sub_gain, drive_gain = voice->drive_gain;
    unsigned drive = params->drive & 127;
    /* Both phases always advance, including where MORF nearly cancels the
     * second saw. No oscillator reallocation when another note is played. */
    uint32_t first = voice->phase[0], second = voice->phase[1];
    uint32_t step1 = voice->increments[0], step2 = voice->increments[1];
    uint32_t sub_phase = voice->sub_phase;
    int32_t previous = voice->last, previous2 = voice->previous, previous3 = voice->older;
    for (uint32_t n = 0; n < count; ++n) {
        int32_t value = lookup(table, first) * saw_weight
                      + lookup(table, second) * morph_weight;
        first += step1; second += step2;
        if (sub_gain) value += lookup(ss_sine, sub_phase) * sub_gain;
        sub_phase += base / 2;
        int32_t sample = value >> 15;
        /* Symmetric bounded cubic drive. Zero bypasses it exactly. */
        if (drive) {
            int32_t x = (sample * drive_gain) >> 8;
            if (x > 32767) x = 32767;
            if (x < -32767) x = -32767;
            int32_t square = (x * x) >> 15;
            int32_t cube = (square * x) >> 15;
            sample = x - ((cube * 10923) >> 15);
        }
        int32_t current = (int16_t)sample;
        /* Four-point half-sample interpolation: (-1,9,9,-1)/16. The
         * causal history adds two output samples of latency versus linear,
         * with less high-band droop and weaker interpolation images. The
         * source is bounded to 21846; the filter peak stays below 27308. */
        *output++ = (int16_t)((9*(previous + previous2) - previous3 - current) >> 4);
        if (n < pairs) *output++ = (int16_t)previous;
        else voice->pending = 1;
        previous3 = previous2; previous2 = previous; previous = current;
    }
    voice->last = (int16_t)previous;
    voice->previous = (int16_t)previous2; voice->older = (int16_t)previous3;
    voice->phase[0] = first; voice->phase[1] = second;
    voice->sub_phase = sub_phase;
}

/* Half-rate synthesis leaves headroom for the standard remix. Four-point
 * interpolation has three output samples of latency. Pending preserves the
 * resampler across arbitrary native sub-frame call boundaries. */
void ss_render(struct ss_voice *voice, const struct ss_params *params,
               int16_t *output, uint32_t count) {
    struct ss_params core = *params;
    if (core.increment < 512) core.increment = 512;
    if (core.increment > 0x3e800000u) core.increment = 0x3e800000u;
    core.increment *= 2;
    if (voice->pending && count) {
        *output++ = voice->previous;
        voice->pending = 0; --count;
    }
    while (count) {
        uint32_t chunk = count > 32 ? 32 : count;
        ss_core_render(voice, &core, output, chunk);
        output += chunk;
        count -= chunk;
    }
}
