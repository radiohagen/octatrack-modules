/* SPDX-License-Identifier: MIT
 * Octatrack adapter for the original seven-saw engine.
 * One mono Supersaw voice per marker track; the existing synth owns notes/AMP.
 */
#include <stdint.h>
#include "engine.c"

/* The firmware loader copies .data but does not clear .bss. Explicit
 * initializers plus -fno-zero-initialized-in-bss put these in the image. */
uint8_t ss_active[8] = {0};
uint32_t ss_samples[8] = {0}, ss_unsupported[8] = {0};
static struct ss_voice ss_voices[8] = {0};
static uint8_t ss_descriptor[0x192] = {0};

int ss_marker(const char *path) {
    const char *base = path;
    unsigned i;
    if (!path) return 0;
    for (i = 0; i < 255 && path[i]; ++i)
        if (path[i] == '/') base = path+i+1;
    if (i == 255) return 0;
    const char *name = "FMSYNTH-SUPERSAW";
    for (i = 0; name[i]; ++i)
        if (base[i] != name[i]) return 0;
    return base[i] == '.' || base[i] == '-' || base[i] == 0;
}

static const char *ss_settings(uint32_t address) {
    if (address < 0x100b14f0u || address >= 0x100b14f0u+0x24640u)
        return (const char *)0;
    if ((address-0x100b14f0u) % 0x448u) return (const char *)0;
    return (const char *)(uintptr_t)address;
}

static void ss_activate(uint32_t track, uint8_t selected, uint16_t previous_gain) {
    if (!ss_active[track] || !previous_gain) ss_init(&ss_voices[track]);
    ss_active[track] = selected;
}
void ss_begin(uint32_t track, const uint8_t *state) {
    if (track >= 8) return;
    uint32_t settings = *(volatile uint32_t *)(uintptr_t)(0x800049d8u+0xa8u*track+8);
    uint8_t selected = (uint8_t)ss_marker(ss_settings(settings));
    ss_activate(track, selected, *(const uint16_t *)(state+38));
}

/* Native Synth layouts are pinned by bridge.py. Pitch is a full 32-bit
 * phase increment at 44.1 kHz; output is the native signed 16.16 L/R. */
int ss_fill(uint32_t track, uint8_t *state, const uint16_t *fp,
            int32_t *out, uint32_t n) {
    if (track >= 8 || !ss_active[track]) return 0;
    if (state[80] || n > 32) {
        ++ss_unsupported[track];
        for (uint32_t i = 0; i < n; ++i) out[2*i] = out[2*i+1] = 0;
        return 1;
    }
    struct ss_params params = {
        .increment = *(uint32_t *)(state+12),
        .detune = (fp[1] >> 8) & 127, .mix = (fp[2] >> 8) & 127,
        .sub = (fp[4] >> 8) & 127, .drive = (fp[5] >> 8) & 127
    };
    int16_t audio[32];
    ss_render(&ss_voices[track], &params, audio, n);
    int32_t gain = *(uint16_t *)(state+38)*32768;
    int32_t step = ((int32_t)*(uint32_t *)(state+24)*32768-gain)/16;
    for (uint32_t i = 0; i < n; ++i) {
        gain += step;
        int32_t g = gain > 0 ? gain/32768 : 0;
        if (g > 32768) g = 32768;
        int32_t value = ((audio[i]*g) >> 15)*65536;
        out[2*i] = out[2*i+1] = value;
    }
    *(uint16_t *)(state+38) = (uint16_t)(gain > 0 ? gain/32768 : 0);
    ss_samples[track] += n;
    return 1;
}

static int ss_assigned(uint32_t track) {
    if (track >= 8) return 0;
    uint32_t bank = *(volatile uint32_t *)(uintptr_t)0x46c82456;
    uint32_t part = *(volatile uint8_t *)(uintptr_t)0x100b14cf;
    if (part > 3 || bank < 0x40000000u || bank >= 0x48000000u) return 0;
    const uint8_t *p = (const uint8_t *)(uintptr_t)(bank+6322*part);
    if (p[0x8eda2+track] != 1) return 0;
    uint32_t slot = p[0x8f04b+5*track];
    return slot < 128 && ss_marker(ss_settings(0x100b14f0u+0x448u*slot));
}

uint8_t *ss_page(uint8_t *original, uint32_t track) {
    if (!ss_assigned(track)) return original;
    for (unsigned i=0; i<sizeof(ss_descriptor); ++i) ss_descriptor[i]=original[i];
    const char title[9] = "SUPERSAW";
    for (unsigned i=0; i<9; ++i) ss_descriptor[9+i]=(uint8_t)title[i];
    const char names[6][6]={"PTCH","DETU","MIX","FINE","SUB","DRIV"};
    for (unsigned i=0; i<36; ++i) ss_descriptor[0x16+i]=((const uint8_t *)names)[i];
    /* Keep pitch and cents formatters; other values use the stock decimal
     * formatter/dial and ordinary one-unit handler (no FM ratio snapping). */
    for (unsigned slot=1; slot<6; ++slot) {
        if (slot == 3) continue;
        *(uint32_t *)(ss_descriptor+0xca+4*slot)=0;
        *(uint32_t *)(ss_descriptor+0xfa+4*slot)=0;
        *(uint32_t *)(ss_descriptor+0x12a+4*slot)=0;
    }
    return ss_descriptor;
}
