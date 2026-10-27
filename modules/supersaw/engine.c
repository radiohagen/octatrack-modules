/* SPDX-License-Identifier: MIT */
#include "engine.h"
#include "tables.h"
#include "filter.h"

#if (-1 >> 1) != -1
#error Supersaw fixed-point arithmetic requires arithmetic signed right shift
#endif

static int32_t lookup(const int16_t *table, uint32_t phase) {
    /* A larger table makes each oscillator one bounded read. Round the
     * phase to the closest sample, wrapping naturally at the cycle edge. */
    return table[(phase + 0x100000u) >> 21];
}
/* Cold notes reset audible history, not valid pitch/control coefficients.
 * ss_prepare still checks every key before reuse, including after a steal. */
static void ss_restart(struct ss_voice *voice) {
    for (unsigned i = 0; i < 2; ++i) voice->phase[i] = 0;
    /* A quarter-cycle offset makes subtraction a pulse at zero detune. */
    voice->phase[1] = 0x40000000u;
    voice->sub_phase = 0;
    voice->last = voice->previous = voice->older = 0; voice->pending = 0;
}
void ss_init(struct ss_voice *voice) {
    ss_restart(voice);
    voice->base = voice->controls = voice->bank = 0;
    voice->saw_weight = voice->morph_weight = voice->sub_gain = voice->drive_gain = 0;
    for (unsigned i = 0; i < 2; ++i) voice->increments[i] = 0;
}
/* Keep the cache guard before its arithmetic. Inlining lets GCC hoist
 * control products into every source call, even on a warm cache. */
static __attribute__((noinline)) void ss_prepare(struct ss_voice *voice, const struct ss_params *params) {
    uint32_t base = params->increment;
    /* The native-order word is only a cache key, never serialized. A
     * fixed-size builtin copy is alias-safe and becomes one aligned load;
     * do not unpack four knobs on the overwhelmingly common cache hit. */
    uint32_t controls;
    __builtin_memcpy(&controls, &params->detune, sizeof controls);
    controls &= 0x7f7f7f7fu;
    if (base < 1024) base = 1024;
    if (base > 0x7d000000u) base = 0x7d000000u;
    if (voice->base == base && voice->controls == controls) return;
    unsigned cold = !voice->base;
    unsigned detune = params->detune & 127;
    /* Pitch bends do not change timbre weights; timbre changes do not
     * change oscillator steps or the anti-alias bank. Retain both caches. */
    if (cold || voice->base != base ||
        ((const uint8_t *)&voice->controls)[0] != detune) {
        /* The generated +/- ratios are exact opposites around unity.
         * Signed truncation is symmetric, so derive the positive offset once. */
        int32_t delta = (int32_t)ss_ratios[detune][1] - 1048576;
        uint32_t offset = (uint32_t)(((int32_t)(base >> 16) * delta
                         + (int32_t)(base & 65535) * delta / 65536) / 16);
        voice->increments[0] = base - offset;
        voice->increments[1] = base + offset;
        /* Three threshold steps replace up to seven loop iterations.
         * Keep ordinary shifts/comparisons: the shared emulator does not
         * implement FF1, so a CLZ shortcut could not be image-qualified. */
        uint32_t maximum=base+offset;
        unsigned bank=0;
        if(maximum<=0x07ffffffu) { bank=4;maximum<<=4; }
        if(maximum<=0x1fffffffu) { bank+=2;maximum<<=2; }
        if(maximum<=0x3fffffffu) { ++bank;maximum<<=1; }
        /* Fade the upper half of this safe harmonic bank before the next
         * octave boundary, using sixteen precomputed blends. Adjacent
         * octaves share their endpoint table, avoiding the old E/F jump.
         * Clamp below the richest bank and above the sine-only bank.
         * All selection work is cached; the sample loop is unchanged. */
        unsigned fade=0;
        if(bank && maximum>0x40000000u)
            fade=(maximum-0x40000000u+0x02000000u)>>26;
        voice->bank=bank*16-fade;
    }
    if (cold || voice->controls != controls) {
        unsigned morph = params->morph & 127;
        unsigned sub = params->sub & 127, drive = params->drive & 127;
        int32_t sub_gain = (int32_t)sub * 64;
        int32_t saw_gain = 32768 - sub_gain;
        voice->drive_gain = 256 + (int32_t)drive * 6;
        voice->saw_weight = saw_gain / 2;
        voice->morph_weight = (voice->saw_weight * ss_morph_polarity[morph]) >> 15;
        voice->sub_gain = sub_gain;
    }
    voice->base = base; voice->controls = controls;
}
/* Dispatch optional sub/drive once per block. Compile away their sample
 * branches and table accesses when those controls are zero. */
static __attribute__((always_inline)) inline void ss_source_render(
        struct ss_voice *voice,int16_t *source,unsigned count,unsigned has_sub,unsigned drive) {
    uint32_t base = voice->base;
    const int16_t *table = ss_saws[voice->bank];
    int32_t saw_weight = has_sub ? voice->saw_weight : 16384;
    int32_t morph_weight = voice->morph_weight;
    int32_t sub_gain = voice->sub_gain, drive_gain = voice->drive_gain;
    /* Both phases always advance, including where MORF nearly cancels the
     * second saw. No oscillator reallocation when another note is played. */
    uint32_t first = voice->phase[0], second = voice->phase[1];
    uint32_t step1 = voice->increments[0], step2 = voice->increments[1];
    uint32_t sub_phase = voice->sub_phase;
    /* Native eight-sample blocks otherwise expand into register spills. */
    #pragma GCC unroll 1
    for (uint32_t n = 0; n < count; ++n) {
        int32_t value = lookup(table, first) * saw_weight
                      + lookup(table, second) * morph_weight;
        first += step1; second += step2;
        if (has_sub) value += lookup(ss_sine, sub_phase) * sub_gain;
        if(has_sub)sub_phase += base / 2;
        int32_t sample = value >> 15;
        /* Symmetric bounded cubic drive. Zero bypasses it exactly. */
        if (drive) {
            int32_t x = (sample * drive_gain) >> 8;
            if (x > 32767) x = 32767;
            if (x < -32767) x = -32767;
            /* Eight-unit input grid bounds the waveshaper error to five
             * PCM units. One read replaces three multiplies; DRIV=0
             * still bypasses the waveshaper without quantization. */
            sample=ss_drive_curve[(x+32772)>>3];
        }
        source[n]=(int16_t)sample;
    }
    /* A disabled sub still keeps its phase, but needs one block update. */
    if(!has_sub)sub_phase += count*(base/2);
    voice->phase[0]=first;voice->phase[1]=second;voice->sub_phase=sub_phase;
}
static void ss_core_render(struct ss_voice *voice, const struct ss_params *params,
               int16_t *output, uint32_t output_count,
               struct ss_filter *filter,const struct ss_filter_params *fp,uint32_t stamp) {
    /* ss_render bounds each chunk to 32 output / 16 source samples. */
    uint32_t count = (output_count + 1) / 2;
    uint32_t pairs = output_count / 2;
    ss_prepare(voice, params);
    /* Stage source samples in the upper half of the caller's output.
     * Forward interpolation only overwrites source samples already read,
     * including the final odd sample. No extra per-voice scratch buffer. */
    int16_t *source=output+pairs;
    unsigned drive=params->drive&127;
    if(voice->sub_gain) {
        if(drive)ss_source_render(voice,source,count,1,1);
        else ss_source_render(voice,source,count,1,0);
    } else {
        if(drive)ss_source_render(voice,source,count,0,1);
        else ss_source_render(voice,source,count,0,0);
    }
    int32_t previous=voice->last,previous2=voice->previous,previous3=voice->older;
    if(filter)ss_filter_half(filter,fp,stamp,source,count);
    for(uint32_t n=0;n<count;++n) {
        int32_t current=source[n];
        /* Four-point half-sample interpolation: (-1,9,9,-1)/16. The
         * causal history adds two output samples of latency versus linear,
         * with less high-band droop and weaker interpolation images. The
         * unfiltered source stays below 21847; filtered peaks need the
         * explicit saturation below. */
        int32_t interpolated=(9*(previous + previous2) - previous3 - current) >> 4;
        /* Resonance can reach full scale; bound interpolation overshoot
         * before converting to 16 bits instead of wrapping its polarity. */
        if(filter) {
            if(interpolated>32767)interpolated=32767;
            if(interpolated< -32768)interpolated= -32768;
        }
        *output++ = (int16_t)interpolated;
        if (n < pairs) *output++ = (int16_t)previous;
        else voice->pending = 1;
        previous3 = previous2; previous2 = previous; previous = current;
    }
    voice->last = (int16_t)previous;
    voice->previous = (int16_t)previous2; voice->older = (int16_t)previous3;
}

/* Half-rate synthesis leaves headroom for the standard remix. Four-point
 * interpolation has three output samples of latency. Pending preserves the
 * resampler across arbitrary native sub-frame call boundaries. */
static __attribute__((aligned(16))) void ss_render_impl(struct ss_voice *voice,const struct ss_params *params,
               int16_t *output,uint32_t count,struct ss_filter *filter,
               const struct ss_filter_params *fp,uint32_t stamp) {
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
        ss_core_render(voice, &core, output, chunk,filter,fp,stamp);
        output += chunk;
        count -= chunk;
    }
}

void ss_render(struct ss_voice *voice,const struct ss_params *params,
               int16_t *output,uint32_t count) {
    ss_render_impl(voice,params,output,count,0,0,0);
}
static void ss_render_filtered(struct ss_voice *voice,const struct ss_params *params,
               int16_t *output,uint32_t count,struct ss_filter *filter,
               const struct ss_filter_params *fp,uint32_t stamp) {
    ss_render_impl(voice,params,output,count,filter,fp,stamp);
}

/* Keep the Q15 floor before formatting native 16.16 stereo. Clearing the
 * product's low 15 bits then doubling preserves negative-fraction rounding.
 * The four-point interpolator can reach [-40960,40959] from arbitrary
 * signed-16-bit history. Gain <= 32768 keeps its product in signed int32;
 * unsigned doubling also defines the native wrap bits for such overshoot. */
static inline int32_t ss_output_scale(int32_t sample,int32_t gain,unsigned stereo) {
    int32_t product=sample*gain;
    return stereo?(int32_t)((uint32_t)(product & ~32767)*2u):product>>15;
}
/* Held AMP needs neither ramp accumulation nor per-sample gain shifts.
 * Keep this dispatch after source/filter rendering, so only the small output
 * loop is specialized. Mono unity also avoids its two gain multiplies. */
static __attribute__((always_inline)) inline void ss_output16(struct ss_voice *voice,
        const int16_t *source,int32_t *mix,unsigned previous_gain,unsigned target_gain,
        unsigned filtered,unsigned stereo,unsigned steady,unsigned unity) {
    int32_t p1=voice->last,p2=voice->previous,p3=voice->older;
    int32_t gain=(int32_t)previous_gain*16;
    int32_t step=(int32_t)target_gain-(int32_t)previous_gain;
    #pragma GCC unroll 1
    for(unsigned i=0;i<8;++i) {
        int32_t current=source[i];
        int32_t interpolated=(9*(p1+p2)-p3-current)>>4;
        if(filtered) {
            if(interpolated>32767)interpolated=32767;
            if(interpolated< -32768)interpolated= -32768;
        }
        int32_t first,second;
        if(steady) {
            first=unity?(stereo?(int32_t)((uint32_t)interpolated*65536u):interpolated):ss_output_scale(interpolated,(int32_t)target_gain,stereo);
            second=unity?(stereo?(int32_t)((uint32_t)p1*65536u):p1):ss_output_scale(p1,(int32_t)target_gain,stereo);
        } else {
            gain+=step;first=ss_output_scale(interpolated,gain>>4,stereo);
            gain+=step;second=ss_output_scale(p1,gain>>4,stereo);
        }
        if(stereo) {
            mix[4*i]=mix[4*i+1]=first;
            mix[4*i+2]=mix[4*i+3]=second;
        } else { mix[2*i]+=first;mix[2*i+1]+=second; }
        p3=p2;p2=p1;p1=current;
    }
    voice->last=(int16_t)p1;voice->previous=(int16_t)p2;voice->older=(int16_t)p3;
}
/* Native frames consume interpolation directly into the mix or stereo sink. Keep
 * the general renderer for split/odd frames and for the independent oracle. */
static __attribute__((always_inline)) inline void ss_native16(struct ss_voice *voice,
        const struct ss_params *params, int32_t *mix, unsigned previous_gain,
        unsigned target_gain, struct ss_filter *filter,
        const struct ss_filter_params *fp, uint32_t stamp, unsigned stereo) {
    struct ss_params core=*params;
    if(core.increment<512)core.increment=512;
    if(core.increment>0x3e800000u)core.increment=0x3e800000u;
    core.increment*=2;
    ss_prepare(voice,&core);
    int16_t source[8];
    unsigned drive=params->drive&127;
    if(voice->sub_gain) {
        if(drive)ss_source_render(voice,source,8,1,1);
        else ss_source_render(voice,source,8,1,0);
    } else {
        if(drive)ss_source_render(voice,source,8,0,1);
        else ss_source_render(voice,source,8,0,0);
    }
    if(filter)ss_filter_half(filter,fp,stamp,source,8);
    if(previous_gain==target_gain) {
        if(stereo && target_gain==32768)
            ss_output16(voice,source,mix,previous_gain,target_gain,filter!=0,stereo,1,1);
        else ss_output16(voice,source,mix,previous_gain,target_gain,filter!=0,stereo,1,0);
    } else ss_output16(voice,source,mix,previous_gain,target_gain,filter!=0,stereo,0,0);
}

static __attribute__((noinline)) void ss_mix16(struct ss_voice *voice,
        const struct ss_params *params, int32_t *mix, unsigned previous_gain,
        unsigned target_gain, struct ss_filter *filter,
        const struct ss_filter_params *fp, uint32_t stamp) {
    ss_native16(voice,params,mix,previous_gain,target_gain,filter,fp,stamp,0);
}
static __attribute__((noinline)) void ss_stereo16(struct ss_voice *voice,
        const struct ss_params *params, int32_t *out, unsigned previous_gain,
        unsigned target_gain, struct ss_filter *filter,
        const struct ss_filter_params *fp, uint32_t stamp) {
    ss_native16(voice,params,out,previous_gain,target_gain,filter,fp,stamp,1);
}
