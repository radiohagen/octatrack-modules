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
/* Keep the cache guard before its arithmetic. Inlining lets GCC hoist
 * control products into every source call, even on a warm cache. */
static __attribute__((noinline)) void ss_prepare(struct ss_voice *voice, const struct ss_params *params) {
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
               int16_t *output, uint32_t output_count) {
    /* ss_render bounds each chunk to 32 output / 16 source samples. */
    uint32_t count = (output_count + 1) / 2;
    uint32_t pairs = output_count / 2;
    ss_prepare(voice, params);
    uint32_t base = voice->base;
    const int16_t *table = ss_saws[voice->bank];
    int32_t centre_weight = voice->centre_weight, side_weight = voice->side_weight;
    int32_t sub_gain = voice->sub_gain, drive_gain = voice->drive_gain;
    unsigned drive = params->drive & 127;
    /* Keep one oscillator's phase, increment and weight in registers. The
     * bounded accumulator avoids spilling eight live oscillator lanes on
     * every sample. Phase continuity is independent of external call splitting. */
    int32_t sum[16];
    if (side_weight) {
        /* Seed from the first side oscillator instead of clearing a scratch
         * buffer and then adding that same oscillator. */
        uint32_t phase = voice->phase[0], step = voice->increments[0];
        for (uint32_t n = 0; n < count; ++n) {
            sum[n] = lookup(table, phase);
            phase += step;
        }
        voice->phase[0] = phase;
        for (unsigned lane = 1; lane < 7; ++lane) {
            if (lane == 3) continue;
            phase = voice->phase[lane];
            step = voice->increments[lane];
            uint32_t n = 0;
            /* Four at a time reduces the ColdFire loop overhead. The tail
             * keeps odd and short calls bit-identical to the scalar path. */
            for (; n + 4 <= count; n += 4) {
                sum[n+0] += lookup(table, phase); phase += step;
                sum[n+1] += lookup(table, phase); phase += step;
                sum[n+2] += lookup(table, phase); phase += step;
                sum[n+3] += lookup(table, phase); phase += step;
            }
            for (; n < count; ++n) {
                sum[n] += lookup(table, phase); phase += step;
            }
            voice->phase[lane] = phase;
        }
    } else {
        for (unsigned lane = 0; lane < 7; ++lane)
            if (lane != 3) voice->phase[lane] += voice->increments[lane] * count;
    }
    uint32_t centre_phase = voice->phase[3], sub_phase = voice->sub_phase;
    int32_t previous = voice->last;
    for (uint32_t n = 0; n < count; ++n) {
        int32_t value = side_weight ? sum[n] * side_weight : 0;
        value += lookup(table, centre_phase) * centre_weight;
        centre_phase += voice->increments[3];
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
        /* Interpolate directly into the destination: no temporary source
         * array or second pass. An odd last sample leaves its pair pending. */
        *output++ = (int16_t)((previous + current) >> 1);
        if (n < pairs) *output++ = (int16_t)current;
        else voice->pending = 1;
        previous = current;
    }
    voice->last = (int16_t)previous;
    voice->phase[3] = centre_phase;
    voice->sub_phase = sub_phase;
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
        uint32_t chunk = count > 32 ? 32 : count;
        ss_core_render(voice, &core, output, chunk);
        output += chunk;
        count -= chunk;
    }
}
