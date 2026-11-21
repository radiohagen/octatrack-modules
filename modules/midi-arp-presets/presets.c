/* Native MIDI ARP SETUP presets. No playback hook or persistent module state.
 * Stock edit paths: 0x4007a2ec (LEN/KEY/offset), 0x4007a7d4 (rotation).
 * See README.md for the rhythm sources and the verified storage boundaries.
 */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
#define B8(a) (*(volatile u8 *)(a))
#define B16(a) (*(volatile u16 *)(a))
#define B32(a) (*(volatile u32 *)(a))

struct preset { const char *title; u16 mask; u8 length; signed char offset[16]; };
/* Bit zero is step one; lengths count arp ticks, independent of SPD.
 * These are onset timelines, not swing, velocity or complete genre grooves.
 */
static const struct preset presets[] = {
    {"ARP A:STRAIGHT", 0xffff, 16, {0}},
    {"ARP A:EIGHTHS",  0x5555, 16, {0}},
    {"ARP A:OFFBEAT",  0x4444, 16, {0}},
    {"ARP A:PULSE4",   0x1111, 16, {0}},
    {"ARP A:TRESILLO", 0x0049,  8, {0}},
    {"ARP A:CINQUIL",  0x006d,  8, {0}},
    {"ARP A:SON3-2",   0x1449, 16, {0}},
    {"ARP A:SON2-3",   0x4914, 16, {0}},
    {"ARP A:E5/16",    0x1249, 16, {0}},
    {"ARP A:E7/16",    0x54a9, 16, {0}},
    {"ARP A:E3/7",     0x0015,  7, {0}},
    {"ARP A:E2/5",     0x0005,  5, {0}},
    {"ARP A:E4/9",     0x0055,  9, {0}},
    {"ARP A:E5/12",    0x0295, 12, {0}},
    {"ARP A:OCTPULSE", 0x0055,  8, {0,0,0,0,12,0,12,0}},
    {"ARP A:OCT332",   0x0049,  8, {0,0,0,0,0,0,12,0}},
    /* Offbeat-only Kent-inspired rhythm; quarter-note kick positions omitted. */
    {"ARP A:KENTBASS", 0xa44a, 16, {0}},
    /* Rolling-bass rhythm families; OFFBEAT above is reused, not duplicated. */
    {"ARP A:LATEPUSH", 0x4848, 16, {0}},
    {"ARP A:ROLLER",   0xeeee, 16, {0}},
    {"ARP A:BROKEN",   0xc6a6, 16, {0}},
    {"ARP A:ANSWER",   0x6666, 16, {0}},
    {"ARP A:SEISMIC",  0x4484, 16, {0}},
};
#define COUNT (sizeof(presets) / sizeof(presets[0]))

/* Keep the original octave presets and short timelines byte-identical.
 * Only the six 16-step bass families expose B's ROOT / OCT / OCT+ choice. */
static int bass_family(unsigned index) {
    return index == 2 || (index >= 17 && index < COUNT);
}

static u8 pitch(unsigned index, unsigned version, unsigned step) {
    const struct preset *v = &presets[index];
    unsigned j, ordinal = 0, last = 0;
    if (!version) return (u8)v->offset[step];
    if (!(v->mask & (1u << step))) return 0;
    for (j = 0; j < v->length; ++j) {
        if (!(v->mask & (1u << j))) continue;
        last = j;
        if (j <= step) ++ordinal;
    }
    return (version == 1 ? step == last : !(ordinal & 1)) ? 12 : 0;
}

struct context { u32 bank, part, track; };
static int context(struct context *c) {
    c->bank = B32(0x46c82456);
    c->part = B8(0x100b14cf);
    c->track = B8(0x100b14cc);
    /* Same 16-bank RAM layout as the native editor; reject stale UI globals. */
    return c->part < 4 && c->track < 8 && c->bank >= 0x400e21e0
        && c->bank <= 0x400e21e0 + 15 * 0x9b340
        && (c->bank - 0x400e21e0) % 0x9b340 == 0;
}

/* Derive family AND variation from native bytes, with no hidden UI state.
 * Save/load, Part/track changes and native copy/paste therefore agree. */
static int match_version(void) {
    struct context c;
    unsigned i, j, version;
    if (!context(&c)) return -1;
    u32 p = c.part * 0x18b2;
    u8 len = B8(c.bank + p + 0x8f270 + c.track * 36);
    u16 mask = B16(c.bank + p + 0x905a2 + c.track * 2);
    for (i = 0; i < COUNT; ++i) {
        if (len + 1 != presets[i].length || mask != presets[i].mask) continue;
        for (version = 0; version < (bass_family(i) ? 3u : 1u); ++version) {
            for (j = 0; j < 16; ++j)
                if (B8(c.bank + p + 0x905b2 + c.track * 16 + j)
                    != pitch(i, version, j)) break;
            if (j == 16) return (int)(i * 3 + version);
        }
    }
    return -1;
}

int ap_match(void) {
    int selected = match_version();
    return selected < 0 ? -1 : selected / 3;
}

int ap_version(void) {
    int selected = match_version();
    return selected < 0 ? -1 : selected % 3;
}

/* A publishes the full rhythm; B publishes offsets only. Out-of-range is a
 * no-op. A short interrupt-masked publication prevents an arp tick seeing
 * half a pattern. It does not restart the arp, clear its pool, or emit MIDI.
 */
static void apply(unsigned index, unsigned version, int rhythm) {
    struct context c;
    unsigned j;
    u8 offsets[16];
    u16 sr;
    if (index >= COUNT || version > 2 || (version && !bass_family(index))
        || !context(&c)) return;
    const struct preset *v = &presets[index];
    u32 p = c.part * 0x18b2;
    /* Prepare outside the interrupt-masked publication. */
    for (j = 0; j < 16; ++j) offsets[j] = pitch(index, version, j);
    ((void (*)(void))0x40027de4)(); /* native edit invalidates clipboard undo */
    __asm__ volatile ("move.w %%sr,%0\n\tmove.w #0x2700,%%sr" : "=d"(sr) : : "memory");
    for (j = 0; j < 16; ++j) {
        B8(c.bank + p + 0x905b2 + c.track * 16 + j) = offsets[j];
        B8(0x100a6700 + p + c.track * 16 + j) = offsets[j];
    }
    if (rhythm) {
        B16(c.bank + p + 0x905a2 + c.track * 2) = v->mask;
        B16(0x100a66f0 + p + c.track * 2) = v->mask;
        B8(c.bank + p + 0x8f270 + c.track * 36) = v->length - 1;
        B8(0x100a53be + p + c.track * 36) = v->length - 1;
        B8(0x46c76dee + c.track * 68) = v->length - 1;
    }
    B8(c.bank + 0x95048) |= 1u << c.part;
    B8(0x100b145e) |= 1u << c.part;
    B32(c.bank + 0x9b332) = 1;
    B32(0x100f8598) = 1;
    __asm__ volatile ("move.w %0,%%sr" : : "d"(sr) : "memory");
    ((void (*)(void))0x40027e00)();
}

void ap_apply(unsigned index) {
    apply(index, 0, 1);
}

void ap_select(int delta) {
    int selected, i, version;
    if (!delta) return;
    selected = match_version();
    i = selected < 0 ? -1 : selected / 3;
    version = selected < 0 ? 0 : selected % 3;
    /* Raw reports may contain several encoder ticks. Advance one choice per
     * report, clamped at the ends, so a fast turn cannot jump a whole bank. */
    if (i < 0) i = 0;
    else if (delta > 0 && i < (int)COUNT - 1) ++i;
    else if (delta < 0 && i > 0) --i;
    else return;
    apply((unsigned)i, bass_family((unsigned)i) ? (unsigned)version : 0, 1);
}

void ap_select_version(int delta) {
    int selected, index, version;
    if (!delta) return;
    selected = match_version();
    if (selected < 0) return; /* Never replace an unrecognized custom arp. */
    index = selected / 3;
    if (!bass_family((unsigned)index)) return;
    version = selected % 3;
    if (delta > 0 && version < 2) ++version;
    else if (delta < 0 && version > 0) --version;
    else return;
    apply((unsigned)index, (unsigned)version, 0);
}

void ap_title(void *window, const char *stock_title, const char *extra) {
    static const char *const versions[] = {" B:ROOT", " B:OCT", " B:OCT+"};
    int selected = match_version();
    int i = selected < 0 ? -1 : selected / 3;
    const char *title = i < 0 ? "ARP A:CUSTOM" : presets[i].title;
    char buffer[32], *out = buffer;
    (void)stock_title;
    if (i >= 0 && bass_family((unsigned)i)) {
        while (*title) *out++ = *title++;
        title = versions[selected % 3];
        do { *out++ = *title; } while (*title++);
        title = buffer;
    }
    ((void (*)(void *, const char *, const char *))0x400570b8)
        (window, title, extra);
}

/* SPD stores ticks minus one (24 ticks per quarter). This replaces only its
 * descriptor's formatter, never its encoder, locks, range or clock path.
 * Four-character labels fit the native parameter cell. Unusual divisions
 * and invalid values retain the exact native formatting.
 */
void ap_speed(char *buffer, unsigned value) {
    const char *label = 0;
    switch (value) {
    case 0: label = "64T"; break;
    case 1: label = "32T"; break;
    case 2: label = "1/32"; break;
    case 3: label = "16T"; break;
    case 5: label = "1/16"; break;
    case 7: label = "8T"; break;
    case 8: label = "16D"; break;
    case 11: label = "1/8"; break;
    case 15: label = "4T"; break;
    case 17: label = "8D"; break;
    case 23: label = "1/4"; break;
    case 31: label = "2T"; break;
    case 35: label = "4D"; break;
    case 47: label = "1/2"; break;
    case 63: label = "1T"; break;
    case 71: label = "2D"; break;
    case 95: label = "1/1"; break;
    }
    if (!label) {
        ((void (*)(char *, unsigned))0x4003b840)(buffer, value);
        return;
    }
    do { *buffer++ = *label; } while (*label++);
}
