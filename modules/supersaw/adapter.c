/* SPDX-License-Identifier: MIT
 * Octatrack adapter for the original two-saw engine.
 * Up to four Supersaw notes per track; the existing synth owns notes/AMP.
 */
#include <stdint.h>
#include "engine.c"
#include "filter.h"

/* The firmware loader copies .data but does not clear .bss. Explicit
 * initializers plus -fno-zero-initialized-in-bss put these in the image. */
uint8_t ss_active[8] = {0};
uint32_t ss_samples[8] = {0}, ss_unsupported[8] = {0};
static struct ss_voice ss_voices[8] = {0};
static struct ss_voice ss_poly_voices[8][4] = {0};
uint32_t ss_poly_samples[8][4] = {{0}};
struct ss_filter ss_filters[8][5] = {{{0}}};
uint8_t ss_setup[8][6] = {{0}};
uint32_t ss_note_stamp[8] = {0};
uint32_t ss_filter_samples[8] = {0};
static uint8_t ss_descriptor[0x192] = {0};
static uint8_t ss_lfo_descriptor[0x192] = {0};

void ss_config(unsigned track);
static int ss_assigned(uint32_t track);
uint8_t *ss_page(uint8_t *original,uint32_t track);
void ss_type_fmt(char *out,int value);
void ss_fine_fmt(char *out,int value);

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
    if (!ss_active[track])
        for (unsigned v=0;v<4;++v) {
            ss_init(&ss_poly_voices[track][v]);
            ss_filter_reset(&ss_filters[track][v]);
        }
    if (!ss_active[track] || !previous_gain) {
        ss_init(&ss_voices[track]);ss_filter_reset(&ss_filters[track][4]);
    }
    ss_active[track] = selected;
}
void ss_begin(uint32_t track, const uint8_t *state) {
    if (track >= 8) return;
    uint32_t settings = *(volatile uint32_t *)(uintptr_t)(0x800049d8u+0xa8u*track+8);
    uint8_t selected = (uint8_t)ss_marker(ss_settings(settings));
    if(selected) { ++ss_note_stamp[track];ss_config(track); }
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
        .detune = (fp[1] >> 8) & 127, .morph = (fp[2] >> 8) & 127,
        .sub = (fp[4] >> 8) & 127, .drive = (fp[5] >> 8) & 127
    };
    int16_t audio[32];
    ss_render(&ss_voices[track], &params, audio, n);
    struct ss_filter_params f={(fp[3]>>8)&127,ss_setup[track][1],ss_setup[track][2],ss_setup[track][3],ss_setup[track][4]};
    if(f.type || ss_filters[track][4].wet) {
        ss_filter_run(&ss_filters[track][4],&f,ss_note_stamp[track],audio,n);
        ss_filter_samples[track]+=n;
    }
    /* A held AMP level needs no per-sample ramp arithmetic. */
    uint32_t previous = *(uint16_t *)(state+38);
    if (*(uint32_t *)(state+24) == previous) {
        int32_t g = previous > 32768 ? 32768 : previous;
        if (g == 32768) {
            for (uint32_t i = 0; i < n; ++i)
                out[2*i] = out[2*i+1] = audio[i]*65536;
        } else {
            for (uint32_t i = 0; i < n; ++i)
                out[2*i] = out[2*i+1] = ((audio[i]*g) >> 15)*65536;
        }
        ss_samples[track] += n;
        return 1;
    }
    /* Four fractional bits represent every step of the native 16-sample
     * ramp exactly. Q15 had redundant precision and could overflow on a
     * 32-sample maximum attack; Q4 also removes two control multiplies. */
    int32_t gain = *(uint16_t *)(state+38)*16;
    int32_t step = (int32_t)*(uint32_t *)(state+24) - *(uint16_t *)(state+38);
    for (uint32_t i = 0; i < n; ++i) {
        gain += step;
        int32_t g = gain > 0 ? gain/16 : 0;
        if (g > 32768) g = 32768;
        int32_t value = ((audio[i]*g) >> 15)*65536;
        out[2*i] = out[2*i+1] = value;
    }
    *(uint16_t *)(state+38) = (uint16_t)(gain > 0 ? gain/16 : 0);
    ss_samples[track] += n;
    return 1;
}

/* The bridge pins the native pool layout: four 64-byte records per track.
 * Native code owns allocation, MIDI/chord identity, pitch and AMP targets.
 * We own oscillator and filter history. Warm steals retain phase; their
 * new note stamp retriggers the independent filter envelope. */
void ss_carry(uint32_t track, uint32_t voice, uint32_t stamp) {
    if (track < 8 && voice < 4 && ss_active[track]) {
        /* Volatile byte copy: freestanding ColdFire has no libc memcpy. */
        volatile uint8_t *dst=(volatile uint8_t *)&ss_poly_voices[track][voice];
        const uint8_t *src=(const uint8_t *)&ss_voices[track];
        for (unsigned i=0;i<sizeof(struct ss_voice);++i) dst[i]=src[i];
        dst=(volatile uint8_t *)&ss_filters[track][voice];
        src=(const uint8_t *)&ss_filters[track][4];
        for(unsigned i=0;i<sizeof(struct ss_filter);++i)dst[i]=src[i];
        /* This is the same sounding note, now identified by native V_AGE. */
        ss_filters[track][voice].stamp=stamp;
    }
}

int ss_track_fill(uint32_t track, uint8_t *state, const uint16_t *fp,
                  int32_t *out, uint32_t n, uint8_t *pool) {
    if (track >= 8 || !ss_active[track]) return 0;
    if (n > 32) {
        ++ss_unsupported[track];
        for (uint32_t i=0;i<n;++i) out[2*i]=out[2*i+1]=0;
        return 1;
    }
    if (!n) return 1;
    unsigned active=0;
    for (unsigned v=0;v<4;++v) active |= pool[v*64+36];
    int32_t mix[32];
    if (!state[80]) {
        ss_fill(track,state,fp,out,n);
        if (!active) return 1; /* No poly tail: the mono render is already complete. */
        for (uint32_t i=0;i<n;++i) mix[i]=out[2*i]>>16;
    } else {
        *(uint16_t *)(state+38)=0;
        ss_samples[track]+=n;
        /* Accumulate directly; no zero stereo pass followed by a copy. */
        for (uint32_t i=0;i<n;++i) mix[i]=0;
    }
    struct ss_params params = {0,(fp[1]>>8)&127,(fp[2]>>8)&127,
                                 (fp[4]>>8)&127,(fp[5]>>8)&127};
    const struct ss_filter_params f={(fp[3]>>8)&127,ss_setup[track][1],ss_setup[track][2],ss_setup[track][3],ss_setup[track][4]};
    for (unsigned v=0;v<4;++v) {
        uint8_t *native=pool+v*64;
        if (!native[36]) continue;
        uint32_t previous=*(uint16_t *)(native+60);
        uint32_t target=*(uint32_t *)(native+24);
        if (!previous) { ss_init(&ss_poly_voices[track][v]);ss_filter_reset(&ss_filters[track][v]); }
        /* Native poly gains are <=32767; bound malformed state as well. */
        if (previous>32767) previous=32767;
        if (target>32767) target=32767;
        params.increment=*(uint32_t *)(native+12);
        int16_t audio[32];
        ss_render(&ss_poly_voices[track][v],&params,audio,n);
        if(f.type || ss_filters[track][v].wet) {
            ss_filter_run(&ss_filters[track][v],&f,*(uint32_t *)(native+48),audio,n);
            ss_filter_samples[track]+=n;
        }
        if (previous==target) {
            for (uint32_t i=0;i<n;++i) mix[i]+=(audio[i]*(int32_t)target)>>15;
        } else {
            /* Match native po_fill: reach the target over this call, Q16.
             * +/-32767 bounds keep the step and accumulator in int32. */
            int32_t gain=(int32_t)previous*65536;
            int32_t step=((int32_t)target-(int32_t)previous)*65536/(int32_t)n;
            for (uint32_t i=0;i<n;++i) {
                gain+=step;
                mix[i]+=(audio[i]*(gain>>16))>>15;
            }
        }
        *(uint16_t *)(native+60)=(uint16_t)target;
        ss_poly_samples[track][v]+=n;
    }
    /* Up to four notes plus a fading mono transition: accumulate before
     * saturation, never add signed 16.16 values that can wrap. */
    for (uint32_t i=0;i<n;++i) {
        int32_t value=mix[i];
        if (value>32767) value=32767;
        if (value< -32768) value= -32768;
        out[2*i]=out[2*i+1]=value*65536;
    }
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
    ss_config(track);
    for (unsigned i=0; i<sizeof(ss_descriptor); ++i) ss_descriptor[i]=original[i];
    const char title[9] = "SUPERSAW";
    for (unsigned i=0; i<9; ++i) ss_descriptor[9+i]=(uint8_t)title[i];
    const char names[6][6]={"PTCH","DETU","MORF","CUT","SUB","DRIV"};
    for (unsigned i=0; i<36; ++i) ss_descriptor[0x16+i]=((const uint8_t *)names)[i];
    /* Keep pitch formatter; other values use the stock decimal
     * formatter/dial and ordinary one-unit handler (no FM ratio snapping). */
    for (unsigned slot=1; slot<6; ++slot) {

        *(uint32_t *)(ss_descriptor+0xca+4*slot)=0;
        *(uint32_t *)(ss_descriptor+0xfa+4*slot)=0;
        *(uint32_t *)(ss_descriptor+0x12a+4*slot)=0;
    }
    const char setup[6][6]={"FINE","RES","ENV","DEC","TYPE",""};
    for(unsigned i=0;i<36;++i)ss_descriptor[0x3a+i]=((const uint8_t *)setup)[i];
    for(unsigned i=6;i<12;++i) {
        *(uint32_t *)(ss_descriptor+0x6a+4*i)=0;
        *(uint32_t *)(ss_descriptor+0x9a+4*i)=i==10?4:i==11?1:128;
        *(uint32_t *)(ss_descriptor+0xca+4*i)=0;
        *(uint32_t *)(ss_descriptor+0xfa+4*i)=0;
        *(uint32_t *)(ss_descriptor+0x12a+4*i)=0;
    }
    *(uint32_t *)(ss_descriptor+0xca+24)=(uint32_t)(uintptr_t)ss_fine_fmt;
    *(uint32_t *)(ss_descriptor+0xca+40)=(uint32_t)(uintptr_t)ss_type_fmt;
    /* Native four-position select, matching TYPE's four stored values. */
    *(uint32_t *)(ss_descriptor+0xfa+40)=0x40046c28u;
    *(uint32_t *)(ss_descriptor+0x18a)=0x00000000;
    *(uint32_t *)(ss_descriptor+0x18e)=0x55555555;
    /* Nibbles 6..10 live; nibble 11 disabled (across the two words). */
    *(uint32_t *)(ss_descriptor+0x18a)=0x00000155;
    return ss_descriptor;
}

uint8_t *ss_lfo_page(uint8_t *original,unsigned track) {
    if(!ss_assigned(track))return original;
    for(unsigned i=0;i<sizeof(ss_lfo_descriptor);++i)ss_lfo_descriptor[i]=original[i];
    for(unsigned i=0;i<6;++i)ss_lfo_descriptor[0x16+30+i]=0;
    *(uint32_t *)(ss_lfo_descriptor+0x18e)&=0xff0fffff;
    *(uint32_t *)(ss_lfo_descriptor+0x6a+20)=0;
    *(uint32_t *)(ss_lfo_descriptor+0x9a+20)=1;
    return ss_lfo_descriptor;
}
#include "ui.h"
