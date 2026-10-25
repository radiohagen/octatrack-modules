/* SPDX-License-Identifier: MIT
 * Octatrack POC adapter. The pinned Digisophie engine is unmodified.
 * One mono FUSE voice per marker track; the existing synth owns notes/AMP.
 */
#include <stdint.h>
#include "upstream/sophie.h"
#include "upstream/sophie.c"

uint8_t sf_active[8];
uint32_t sf_samples[8], sf_unsupported[8];
struct sf_voice {
    struct ds_voice engine;
    struct ds_params params;
    int32_t block[32];
    int32_t left, right;
    uint32_t pos, fraction, pitch_inc, resample_step;
    uint8_t primed, trigger;
};
static struct sf_voice sf_voices[8];
static uint8_t sf_descriptor[0x192];

/* Q16 interpolation weights for source positions 0..146 of 147. The
 * maximum product is 65535 * 65090, which fits in uint32_t. This replaces
 * one long division per output sample with a multiply and shift. */
static const uint16_t sf_interp_q16[147] = {
    0, 446, 892, 1337, 1783, 2229, 2675, 3121, 3567, 4012,
    4458, 4904, 5350, 5796, 6242, 6687, 7133, 7579, 8025, 8471,
    8916, 9362, 9808, 10254, 10700, 11146, 11591, 12037, 12483, 12929,
    13375, 13821, 14266, 14712, 15158, 15604, 16050, 16495, 16941, 17387,
    17833, 18279, 18725, 19170, 19616, 20062, 20508, 20954, 21400, 21845,
    22291, 22737, 23183, 23629, 24074, 24520, 24966, 25412, 25858, 26304,
    26749, 27195, 27641, 28087, 28533, 28979, 29424, 29870, 30316, 30762,
    31208, 31653, 32099, 32545, 32991, 33437, 33883, 34328, 34774, 35220,
    35666, 36112, 36557, 37003, 37449, 37895, 38341, 38787, 39232, 39678,
    40124, 40570, 41016, 41462, 41907, 42353, 42799, 43245, 43691, 44136,
    44582, 45028, 45474, 45920, 46366, 46811, 47257, 47703, 48149, 48595,
    49041, 49486, 49932, 50378, 50824, 51270, 51715, 52161, 52607, 53053,
    53499, 53945, 54390, 54836, 55282, 55728, 56174, 56620, 57065, 57511,
    57957, 58403, 58849, 59294, 59740, 60186, 60632, 61078, 61524, 61969,
    62415, 62861, 63307, 63753, 64199, 64644, 65090
};

static int32_t sf_interpolate(int32_t difference, uint32_t fraction) {
    uint32_t magnitude = difference < 0 ? 0u - (uint32_t)difference
                                      : (uint32_t)difference;
    uint32_t part = (magnitude * sf_interp_q16[fraction]) >> 16;
    return difference < 0 ? -(int32_t)part : (int32_t)part;
}

int sf_marker(const char *path) {
    const char *base = path;
    unsigned i;
    if (!path) return 0;
    for (i = 0; i < 255 && path[i]; ++i)
        if (path[i] == '/') base = path+i+1;
    if (i == 255) return 0;
    const char *name = "FMSYNTH-SOPHIE";
    for (i = 0; name[i]; ++i)
        if (base[i] != name[i]) return 0;
    return base[i] == '.' || base[i] == '-' || base[i] == 0;
}

static const char *sf_settings(uint32_t address) {
    if (address < 0x100b14f0u || address >= 0x100b14f0u+0x24640u)
        return (const char *)0;
    if ((address-0x100b14f0u) % 0x448u) return (const char *)0;
    return (const char *)(uintptr_t)address;
}

void sf_begin(uint32_t track) {
    if (track >= 8) return;
    uint32_t settings = *(volatile uint32_t *)(uintptr_t)(0x800049d8u+0xa8u*track+8);
    uint8_t selected = (uint8_t)sf_marker(sf_settings(settings));
    struct sf_voice *v = &sf_voices[track];
    if (!sf_active[track]) ds_voice_init(&v->engine);
    sf_active[track] = selected;
    v->trigger = 1;
    v->primed = 0;
    v->pos = 32;
    v->fraction = 0;
    v->pitch_inc = 0;
    v->resample_step = 0;
}

static int32_t sf_next(struct sf_voice *v) {
    if (v->pos == 32) {
        ds_voice_render(&v->engine, &v->params, v->trigger, v->block, 32);
        v->trigger = 0;
        v->pos = 0;
    }
    return v->block[v->pos++] / 65536;
}

/* Native sy_state and parameter-record layouts, pinned by bridge.py.
 * DSP source samples are interleaved signed 16.16 L/R.
 * The original engine produces 48 kHz frames (24 kHz oscillators). Keep
 * its coefficients and control cadence, resample 160:147 to 44.1 kHz.
 */
int sf_fill(uint32_t track, uint8_t *state, const uint16_t *fp,
            int32_t *out, uint32_t n) {
    if (track >= 8 || !sf_active[track]) return 0;
    if (state[80] || n > 32) { /* Unsupported polyphony is silent, never FM. */
        ++sf_unsupported[track];
        for (uint32_t i=0; i<n; ++i) out[2*i]=out[2*i+1]=0;
        return 1;
    }
    struct sf_voice *v = &sf_voices[track];
    uint32_t inc = *(uint32_t *)(state+12);
    /* The upstream oscillator accepts only an integer phase increment.
     * At low notes that rounds many adjacent FINE values to the same pitch.
     * Keep that oscillator unchanged and carry the lost fraction in the
     * 48 kHz -> 44.1 kHz source step. 147 * 65536 is one source frame. */
    if (inc != v->pitch_inc || !v->resample_step) {
        uint32_t raw_phase = (inc >> 8)*147u/40960u;
        uint32_t phase = raw_phase;
        if (phase < 8) phase = 8;
        if (phase > 24576) phase = 24576;
        v->params.phase_inc = (uint16_t)phase;
        v->pitch_inc = inc;
        if (raw_phase < 8 || raw_phase > 24576) {
            v->resample_step = 160u * 65536u;
        } else {
            /* Split the quotient so ColdFire needs no 64-bit divide. */
            uint32_t whole = inc / phase, rem = inc % phase;
            v->resample_step = whole * 147u + (rem * 147u + phase / 2u) / phase;
        }
    }
    v->params.model = 0;  /* FUSE: the first proof-of-concept model. */
    v->params.color = (uint8_t)(fp[1] >> 8) & 127;
    v->params.metal = (uint8_t)(fp[2] >> 8) & 127;
    v->params.feedback = (uint8_t)(fp[4] >> 8) & 127;
    v->params.sweep = (int8_t)(((fp[5] >> 8) & 127)-64);
    v->params.velocity = 127;
    v->params.fold = 0;
    int32_t gain = *(uint16_t *)(state+38)*32768;
    int32_t step = ((int32_t)*(uint32_t *)(state+24)*32768-gain)/16;
    if (!v->primed) {
        v->left = sf_next(v); v->right = sf_next(v); v->primed = 1;
    }
    for (uint32_t i=0; i<n; ++i) {
        int32_t sample = v->left+sf_interpolate(v->right-v->left,
                                                v->fraction >> 16);
        gain += step;
        int32_t g = gain > 0 ? gain/32768 : 0;
        if (g > 32768) g=32768;
        /* Upstream's fixed conditioning peaks at about -12 dBFS for FUSE.
         * Restore 6 dB before the normal Octatrack AMP/mixer path. */
        int32_t value = (sample*g/32768)*2;
        if (value > 32767) value = 32767;
        if (value < -32768) value = -32768;
        value *= 65536;
        out[2*i] = out[2*i+1] = value;
        v->fraction += v->resample_step;
        while (v->fraction >= 147u * 65536u) {
            v->fraction -= 147u * 65536u;
            v->left = v->right; v->right = sf_next(v);
        }
    }
    *(uint16_t *)(state+38) = (uint16_t)(gain > 0 ? gain/32768 : 0);
    sf_samples[track] += n;
    return 1;
}

static int sf_assigned(uint32_t track) {
    if (track >= 8) return 0;
    uint32_t bank = *(volatile uint32_t *)(uintptr_t)0x46c82456;
    uint32_t part = *(volatile uint8_t *)(uintptr_t)0x100b14cf;
    if (part > 3 || bank < 0x40000000u || bank >= 0x48000000u) return 0;
    const uint8_t *p = (const uint8_t *)(uintptr_t)(bank+6322*part);
    if (p[0x8eda2+track] != 1) return 0;
    uint32_t slot = p[0x8f04b+5*track];
    return slot < 128 && sf_marker(sf_settings(0x100b14f0u+0x448u*slot));
}

uint8_t *sf_page(uint8_t *original, uint32_t track) {
    if (!sf_assigned(track)) return original;
    for (unsigned i=0; i<sizeof(sf_descriptor); ++i) sf_descriptor[i]=original[i];
    const char title[9] = "SOPHIE";
    for (unsigned i=0; i<9; ++i) sf_descriptor[9+i]=(uint8_t)title[i];
    const char names[6][6]={"PTCH","COLR","METL","FINE","FBK","SWEP"};
    for (unsigned i=0; i<36; ++i) sf_descriptor[0x16+i]=((const uint8_t *)names)[i];
    /* Keep pitch and cents formatters; other values use the stock decimal
     * formatter/dial and ordinary one-unit handler (no FM ratio snapping). */
    for (unsigned slot=1; slot<6; ++slot) {
        if (slot == 3) continue;
        *(uint32_t *)(sf_descriptor+0xca+4*slot)=0;
        *(uint32_t *)(sf_descriptor+0xfa+4*slot)=0;
        *(uint32_t *)(sf_descriptor+0x12a+4*slot)=0;
    }
    return sf_descriptor;
}
