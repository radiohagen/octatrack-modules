/* Native LFO adapters and editor. Card/Part lifecycle lives in storage.c. */
#include "lifecycle.h"
#include "retention.h"
#include "encoder.h"
#define U8(a) (*(volatile uint8_t *)(uintptr_t)(a))
#define U32(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define BANK_BASE 0x400e21e0u
#define BANK_STRIDE 0x9b340u
#define PART_STRIDE 0x18b2u

/* Loader-owned initialized memory. Never borrow native designer bytes. */
EulBank eul_bank[16] __attribute__((section(".data"))) = {{{{0}}}};
static EulState eul_states[EUL_LANES] __attribute__((section(".data"))) = {0};
static unsigned eul_context[EUL_LANES] __attribute__((section(".data"))) = {0};
static unsigned eul_clock_context[EUL_LANES] __attribute__((section(".data"))) = {0};
static int32_t eul_remainder[EUL_LANES] __attribute__((section(".data"))) = {0};
static EulAudioClock eul_audio_clocks[24] __attribute__((section(".data"))) = {{0}};
unsigned eul_editing=0, eul_page=0;
/* Design comparison only: 0 = native SETUP split, 1 = full-width grid.
 * No panel control or persisted setting is assigned to this test selector. */
unsigned eul_ui_style=0;
static unsigned edit_bank=0, edit_part=0, edit_lane=0;
static int edit_residue[6]={0};
static void reset_encoders(void) {
    for(unsigned i=0;i<6;++i) edit_residue[i]=0;
}
static volatile unsigned eul_loading=0;
static EulParams eul_clips[2][EUL_LANES] __attribute__((section(".data")))={{{0}}};
static unsigned eul_clip_valid[2] __attribute__((section(".data")))={0};
static void changed(unsigned bank,unsigned part,unsigned lane);
extern void eul_stock_draw(void);

static unsigned clock_steps(unsigned index,unsigned midi) {
    if(index>=24) return 0;
    unsigned track=index/3, id=index+(midi?24:0);
    unsigned bank=U8(0x8000182au+track), part=U8(0x80001832u+track);
    if(bank>=16 || part>=4) { bank=U8(0x80001828u); part=U8(0x80001829u); }
    if(bank>=16 || part>=4) return 0;
    unsigned steps=eul_bank[bank][part][id].steps;
    if(!steps) steps=8; else if(steps>16) steps=16;
    unsigned context=1+steps+32*(part+4*bank);
    if(eul_clock_context[id]!=context) {
        eul_remainder[id]=0; eul_clock_context[id]=context;
    }
    return steps;
}
int32_t eul_scale_increment(int32_t increment,unsigned index,unsigned midi) {
    unsigned steps=clock_steps(index,midi);
    return steps?eul_clock(increment,steps,&eul_remainder[index+(midi?24:0)]):increment;
}
int32_t eul_scale_audio(int32_t increment,unsigned index,int speed,unsigned mult) {
    unsigned steps=clock_steps(index,0), tempo=U32(0x8000181cu);
    if(!steps) return increment;
    /* Defensive overflow boundary, above the native 300 BPM maximum.
     * Invalid live data must not enter either clock with a stale residue. */
    if(tempo>8191 || mult>6) { eul_remainder[index]=0; return increment; }
    return eul_audio_clock_cached(&eul_audio_clocks[index],speed,tempo,mult,steps,&eul_remainder[index]);
}

void eul_wave(uint32_t *native,unsigned index,unsigned midi,unsigned reset) {
    if (index>=24) { native[1]=0; return; }
    unsigned track=index/3, lane=index%3;
    unsigned bank=U8(0x8000182au+track), part=U8(0x80001832u+track);
    if (bank>=16 || part>=4) { bank=U8(0x80001828u); part=U8(0x80001829u); }
    if (bank>=16 || part>=4) { native[1]=0; return; }
    unsigned id=index+(midi?24:0);
    unsigned context=1+part+4*bank;
    if (eul_context[id]!=context) {
        eul_states[id].ready=0; eul_context[id]=context;
    }
    unsigned trig=midi ? U8(0x46c76dc0u+68*track+0x41+lane)
        : U8(0x80000510u+(U32(0x800000e0u)&1)*0x180+48*track+0x27+lane);
    trig&=7;
    unsigned terminal=((trig==4 || trig==7) && native[0]>=EUL_PHASE/2)
                      || native[0]>=EUL_PHASE;
    /* Native d0 also marks a free-running wrap; that is not a retrigger. */
    native[1]=(uint32_t)eul_process(&eul_states[id],&eul_bank[bank][part][id],
                                   native[0],reset && trig && !native[0],terminal,id);
}
static unsigned selected(unsigned *bank,unsigned *part,unsigned *id) {
    unsigned t=U8(0x100b14ccu), p=U8(0x100b14cfu), b=U8(0x80000002u);
    unsigned lane=U32(0x460d1a32u), midi=U32(0x80000012u)!=0;
    if (!U32(0x400bc038u) || t>=8 || p>=4 || b>=16 || lane>=3) return 0;
    unsigned address=BANK_BASE+BANK_STRIDE*b+0x8ed80+PART_STRIDE*p;
    address+=(midi ? 0x4e8+36*t : 0x2f2+30*t)+3+lane;
    if ((U8(address)&127)!=19) return 0;
    *bank=b; *part=p; *id=t*3+lane+(midi?24:0);
    return 1;
}
static EulParams *editing(void) {
    unsigned b,p,id;
    if (!eul_editing || eul_loading) return 0;
    if (!selected(&b,&p,&id) || b!=edit_bank || p!=edit_part || id!=edit_lane) {
        eul_editing=0; return 0;
    }
    return &eul_bank[b][p][id];
}
static void text(void *surface,int x,int y,const char *str) {
    ((void (*)(unsigned,void *,int,int,int,const char *))0x40012bd8u)
        (0x400ba876u,surface,x,y,-1,str);
}
enum { EUL_RATE_FIELD=11, EUL_RATES=13 };
static const uint8_t eul_fields[2][6]={{0,1,2,6,7,8},{3,4,5,9,EUL_DIRECTION_FIELD,EUL_RATE_FIELD}};
static const uint8_t rate_speeds[EUL_RATES]={8,16,24,32,48,64,96,64,96,64,96,64,96};
static const uint8_t rate_mults[EUL_RATES]={0,0,0,0,0,0,0,1,1,2,2,3,3};
static const char *const rate_labels[EUL_RATES]={"1/1","1/2","2T","1/4","4T","1/8","8T","1/16","16T","1/32","32T","1/64","64T"};
static unsigned rate_writing=0;
static unsigned rate_product(void) {
    unsigned midi=edit_lane>=24, track=edit_lane%24/3, lane=edit_lane%3;
    unsigned part=BANK_BASE+BANK_STRIDE*edit_bank+0x8ed80+PART_STRIDE*edit_part;
    unsigned speed=U8(part+(midi?0x3e8+32*track:0x11a+24*track)+lane);
    unsigned mult=U8(part+(midi?0x500+36*track:0x30a+30*track)+lane);
    return speed<<(mult>6?6:mult);
}
static unsigned rate_index(unsigned product) {
    unsigned i=0;
    while(i+1<EUL_RATES && product>((unsigned)rate_speeds[i]<<rate_mults[i])) ++i;
    return i;
}
extern void eul_rate_mult(unsigned value,unsigned lane,unsigned part_address,
                          unsigned sram_base,unsigned live_base);
static unsigned rate_edit(int delta) {
    if(!delta) return 0;
    unsigned product=rate_product(), i=rate_index(product);
    /* VAR rounds to the next division in the direction turned. STOP starts
     * at 1/16. Native saved SPD is 0-127; subsequent native SPD/MULT edits
     * remain possible and are reflected here without a second saved rate. */
    unsigned preset=(unsigned)rate_speeds[i]<<rate_mults[i];
    int next=product?(int)i+delta-(product<preset && delta>0)
        +(product>preset && delta<0):7;
    if(next<0) next=0; else if(next>=EUL_RATES) next=EUL_RATES-1;
    if(product==((unsigned)rate_speeds[next]<<rate_mults[next])) return 0;
    unsigned midi=edit_lane>=24,track=edit_lane%24/3,lane=edit_lane%3;
    unsigned part=BANK_BASE+BANK_STRIDE*edit_bank+0x8ed80+PART_STRIDE*edit_part;
    /* Both native writers refresh their caller. Present one final frame,
     * not the transient old-SPD/new-MULT combination and then another draw. */
    rate_writing=1;
    ((void (*)(void))0x40027e00u)();
    eul_rate_mult(rate_mults[next],lane,
        part+(midi?0x500+36*track:0x30a+30*track)+lane,
        (midi?0x100a53ceu+36*track:0x100a51d8u+30*track)+PART_STRIDE*edit_part,
        midi?0x46c76dc0u+68*track+0x3e:0x8000084eu+72*track);
    ((int (*)(unsigned,unsigned,int))0x40054cd8u)(track+(midi?8:0),6+lane,
        rate_speeds[next]);
    rate_writing=0;
    return 1;
}
static unsigned display_value=0;
static const char *display_word=0;
static void eul_format(char *out,int ignored) {
    (void)ignored;
    if(display_word) {
        const char *word=display_word;
        while(*word) *out++=*word++;
    } else {
        if(display_value>=100) *out++=(char)('0'+display_value/100);
        if(display_value>=10) *out++=(char)('0'+display_value/10%10);
        *out++=(char)('0'+display_value%10);
    }
    *out=0;
}
static void centered(void *surface,int x,int y,const char *str) {
    int width=((int (*)(unsigned,int,const char *))0x40012f30u)(0x400ba876u,-1,str);
    text(surface,x-width/2,y,str);
}
void eul_ui_draw(void) {
    if(rate_writing) return;
    EulParams *raw=editing();
    if (!raw) { eul_stock_draw(); return; }
    uint32_t window=U32(0x400bc038u);
    void *surface=(void *)(uintptr_t)(window+36);
    EulParams p=*raw; eul_normalize(&p);
    unsigned mode=p.mode&EUL_SHAPE_MASK;
    ((void (*)(void *,int,int))0x400125acu)(surface,0,1);
    char title[]="EUCLID A1 LFO1 1/2";
    title[7]=edit_lane>=24?'M':'A'; title[8]='1'+edit_lane%24/3;
    title[13]='1'+edit_lane%3; title[15]='1'+eul_page;
    ((void (*)(uint32_t,const char *,const char *))0x400570b8u)(window,title,"");
    const char *labels[]={"STPS","PULS","ROT","OUT",
        mode>=EUL_RAND?"SLEW":mode==EUL_GATE?"EDGE":"ATK",
        mode>=EUL_RAND?"--":mode==EUL_GATE?"LEN":"DEC",
        "ACNT","AROT","BST","SWNG","DIR","RATE"};
    unsigned limits[]={16,p.steps,p.steps-1,3,127,127,p.pulses,p.pulses?p.pulses-1:0,127,30,1,EUL_RATES-1};
    static const char *const modes[]={"ENV","GATE","RAND","LOOP"};
    int left=eul_ui_style?2:52, stride=eul_ui_style?37:20;
    if(!eul_ui_style) {
        ((void (*)(void *,int,int,int,int))0x40011b94u)(surface,52,2,54,1);
        centered(surface,26,48,"PATTERN");
        uint16_t hits,accents; eul_masks(&p,&hits,&accents);
        for(unsigned i=0;i<16;++i)
            centered(surface,10+11*(i%4),37-10*(i/4),i>=p.steps?" ":
                     (accents&(1u<<i))?"*":(hits&(1u<<i))?"o":".");
    }
    ((void (*)(void *,int,int,int))0x40011a58u)(surface,left,28,111);
    for(unsigned col=1;col<3;++col)
        ((void (*)(void *,int,int,int,int,int))0x40012004u)
            (surface,left+stride*col,2,left+stride*col,54,1);
    for (unsigned i=0;i<6;++i) {
        unsigned field=eul_fields[eul_page&1][i];
        if(field>EUL_RATE_FIELD) continue;
        int x=eul_ui_style?11+37*(i%3):53+20*(i%3), y=i<3?29:2;
        if(field==5 && mode>=EUL_RAND) {
            centered(surface,x+9,y+19,labels[field]); centered(surface,x+9,y+1,"--"); continue;
        }
        unsigned product=field==EUL_RATE_FIELD?rate_product():0,rate=rate_index(product);
        unsigned value=field==EUL_RATE_FIELD?rate:field==EUL_DIRECTION_FIELD?!!(p.mode&EUL_NEGATIVE)
            :field==3?mode:((const uint8_t *)&p)[field],limit=limits[field];
        display_word=field==3?modes[mode]:field==EUL_DIRECTION_FIELD?(value?"NEG":"POS"):0;
        if(field==EUL_RATE_FIELD) display_word=!product?"STOP":
            product==((unsigned)rate_speeds[rate]<<rate_mults[rate])?rate_labels[rate]:"VAR";
        display_value=field==9?50+value:value;
        unsigned position=field==0?(value-1)*127/15:limit?value*127/limit:0;
        ((void (*)(int,int,unsigned,int,unsigned,void (*)(char *,int),void *))0x400479b4u)
            (x,y,i,(int)position,8,eul_format,surface);
        /* Stock labels follow the widget: its marker occupies label baseline. */
        centered(surface,x+9,y+19,labels[field]);
    }
    U32(0x46c7c72cu)=1;
}
void eul_ui_yes(unsigned key,unsigned edge) {
    unsigned b,p,id;
    if (selected(&b,&p,&id)) {
        /* Selection can change before the next redraw. YES must open the
         * newly selected lane, not toggle a stale editor and then close it. */
        if (!editing()) { edit_bank=b; edit_part=p; edit_lane=id; eul_page=0; }
        else eul_page^=1;
        reset_encoders(); eul_editing=1; eul_ui_draw();
    } else ((void (*)(unsigned,unsigned))0x4005cbc8u)(key,edge);
}
void eul_ui_no(unsigned key,unsigned edge) {
    if (eul_editing) { eul_editing=0; eul_ui_draw(); }
    else ((void (*)(unsigned,unsigned))0x4005b99cu)(key,edge);
}
void eul_ui_arrow(unsigned key,unsigned edge) {
    if (editing()) {
        unsigned page=key==0x21 || key==0x20;
        if(page!=eul_page) { eul_page=page; reset_encoders(); eul_ui_draw(); }
    }
    else ((void (*)(unsigned,unsigned))(uintptr_t)
        ((key==0x20 || key==0x33)?0x4003a3b4u:0x400321d0u))(key,edge);
}
void eul_ui_encoder(unsigned encoder,int delta) {
    if(eul_loading) return;
    EulParams *p=editing();
    if (!p) { ((void (*)(unsigned,int))0x40038e04u)(encoder,delta); return; }
    if (encoder==6) return; /* LEVEL must not unexpectedly change a pattern. */
    if(encoder>=6) return;
    unsigned field=eul_fields[eul_page&1][encoder];
    if(field==EUL_RATE_FIELD) {
        unsigned product=rate_product(),i=rate_index(product);
        /* VAR outside the presets and STOP must still be able to enter the
         * preset range in either direction. Only exact endpoints clamp. */
        unsigned exact=product==((unsigned)rate_speeds[i]<<rate_mults[i]);
        delta=eul_encoder_turn(field,delta,exact?i+1:1,exact?1:0,
                               exact?EUL_RATES:EUL_RATES+1,&edit_residue[encoder]);
        if(delta && rate_edit(delta)) eul_ui_draw();
        return;
    }
    if (field>EUL_DIRECTION_FIELD || (field==5 && (p->mode&EUL_SHAPE_MASK)>=EUL_RAND)) {
        edit_residue[encoder]=0; return;
    }
    EulParams next=*p; eul_normalize(&next);
    unsigned limits[]={16,next.steps,next.steps-1,3,127,127,next.pulses,
                       next.pulses?next.pulses-1:0,127,30,1};
    unsigned value=field==EUL_DIRECTION_FIELD?!!(next.mode&EUL_NEGATIVE):
        field==3?next.mode&EUL_SHAPE_MASK:((const uint8_t *)&next)[field];
    delta=eul_encoder_turn(field,delta,value,field==0?1:0,limits[field],&edit_residue[encoder]);
    if(!delta) return;
    if (eul_edit(&next,field,delta)) {
        /* Publish ten bytes together: the audio callback must never see
         * STEPS changed but its dependent PULSE/ACCNT values still old.
         * No drawing, file I/O or native calls with interrupts masked. */
        uint16_t sr;
        __asm__ volatile("move.w %%sr,%0\n\tmove.w #0x2700,%%sr" : "=d"(sr) :: "memory");
        *p=next;
        ++eul_revision[edit_bank];
        __asm__ volatile("move.w %0,%%sr" :: "d"(sr) : "memory");
        changed(edit_bank,edit_part,edit_lane);
        if(field==0) { edit_residue[1]=0; edit_residue[2]=0; }
        if(field==0 || field==1) { edit_residue[3]=0; edit_residue[4]=0; }
        if(field==3) { edit_residue[1]=0; edit_residue[2]=0; }
        eul_ui_draw();
    }
}

unsigned eul_current_bank(void) { return U8(0x80000002u); }
#ifndef EUL_SIDECAR_ONLY
volatile uint8_t *eul_nv_memory(void) { return (volatile uint8_t *)(uintptr_t)EUL_NV_BASE; }
#endif
uint16_t eul_nv_lock(void) {
    uint16_t sr;
    __asm__ volatile("move.w %%sr,%0\n\tmove.w #0x2700,%%sr" : "=d"(sr) :: "memory");
    return sr;
}
void eul_nv_unlock(uint16_t sr) {
    __asm__ volatile("move.w %0,%%sr" :: "d"(sr) : "memory");
}
void eul_schedule(unsigned bank) {
    if(bank>=16) return;
    U32(BANK_BASE+BANK_STRIDE*bank+0x9b332u)=1;
    if(bank==eul_current_bank()) U32(0x100f8598u)=1;
    ((void (*)(void))0x40027e00u)();
}
void eul_publish(unsigned bank,const EulBank source) {
    if(bank>=16) return;
    eul_loading=1;
    for(unsigned p=0;p<EUL_PARTS;++p) for(unsigned l=0;l<EUL_LANES;++l) {
        uint16_t sr;
        __asm__ volatile("move.w %%sr,%0\n\tmove.w #0x2700,%%sr" : "=d"(sr) :: "memory");
        eul_bank[bank][p][l]=source[p][l];
        __asm__ volatile("move.w %0,%%sr" :: "d"(sr) : "memory");
    }
    ++eul_revision[bank];
    for(unsigned l=0;l<EUL_LANES;++l)
        if(eul_context[l] && (eul_context[l]-1)/4==bank) {
            eul_context[l]=0; eul_clock_context[l]=0;
        }
    eul_loading=0;
}
void eul_publish_part(unsigned bank,unsigned part,const EulParams *source) {
    if(bank>=16 || part>=EUL_PARTS) return;
    eul_loading=1;
    for(unsigned l=0;l<EUL_LANES;++l) {
        uint16_t sr;
        __asm__ volatile("move.w %%sr,%0\n\tmove.w #0x2700,%%sr" : "=d"(sr) :: "memory");
        eul_bank[bank][part][l]=source[l];
        __asm__ volatile("move.w %0,%%sr" :: "d"(sr) : "memory");
    }
    ++eul_revision[bank];
    if(part<4) for(unsigned l=0;l<EUL_LANES;++l)
        if(eul_context[l]==1+part+4*bank) {
            eul_context[l]=0; eul_clock_context[l]=0;
        }
    eul_loading=0;
    eul_nv_touch_part(bank,part);
}
void eul_finish_write(unsigned bank,unsigned revision) {
    uint16_t sr;
    __asm__ volatile("move.w %%sr,%0\n\tmove.w #0x2700,%%sr" : "=d"(sr) :: "memory");
    eul_dirty[bank]=eul_revision[bank]!=revision;
    __asm__ volatile("move.w %0,%%sr" :: "d"(sr) : "memory");
}
unsigned eul_snapshot(unsigned bank,EulBank dest) {
    if(bank>=16) return 0;
    for(unsigned attempt=0;attempt<3;++attempt) {
        unsigned revision=eul_revision[bank];
        for(unsigned p=0;p<EUL_PARTS;++p) for(unsigned l=0;l<EUL_LANES;++l) {
            uint16_t sr;
            __asm__ volatile("move.w %%sr,%0\n\tmove.w #0x2700,%%sr" : "=d"(sr) :: "memory");
            dest[p][l]=eul_bank[bank][p][l];
            __asm__ volatile("move.w %0,%%sr" :: "d"(sr) : "memory");
        }
        if(eul_revision[bank]==revision) return 1;
    }
    return 0;
}
unsigned eul_snapshot_part(unsigned bank,unsigned part,EulParams *dest) {
    if(bank>=16 || part>=EUL_PARTS) return 0;
    for(unsigned attempt=0;attempt<3;++attempt) {
        unsigned revision=eul_revision[bank];
        for(unsigned l=0;l<EUL_LANES;++l) {
            uint16_t sr;
            __asm__ volatile("move.w %%sr,%0\n\tmove.w #0x2700,%%sr" : "=d"(sr) :: "memory");
            dest[l]=eul_bank[bank][part][l];
            __asm__ volatile("move.w %0,%%sr" :: "d"(sr) : "memory");
        }
        if(eul_revision[bank]==revision) return 1;
    }
    return 0;
}
static unsigned part_address(uint32_t address,unsigned *bank,unsigned *part) {
    if(address<BANK_BASE || address>=BANK_BASE+16*BANK_STRIDE) return 0;
    unsigned off=(address-BANK_BASE)%BANK_STRIDE;
    if(off<0x8ed80 || off>=0x8ed80+4*PART_STRIDE || (off-0x8ed80)%PART_STRIDE) return 0;
    *bank=(address-BANK_BASE)/BANK_STRIDE; *part=(off-0x8ed80)/PART_STRIDE;
    return 1;
}
/* The two capture hooks run AFTER native memcpy, not at the shared call
 * sites owned by PLOCKS P2. Native clipboard-kind checks still own validity
 * and lifetime. Keep the mirror across project changes just like stock. */
void eul_capture_part(const void *src,unsigned which) {
    unsigned bank,part;
    if(which>=2) return;
    eul_clip_valid[which]=part_address((uint32_t)(uintptr_t)src,&bank,&part) &&
        eul_snapshot_part(bank,part,eul_clips[which]);
}
/* Scoped to Part Reload/Paste's local memcpy pointers. Eight-byte scratch
 * and native CS1 mirror copies remain plain native copies. */
void *eul_part_copy(void *dst,const void *src,unsigned size) {
    void *result=((void *(*)(void *,const void *,unsigned))0x40020898u)(dst,src,size);
    uint32_t d=(uint32_t)(uintptr_t)dst,s=(uint32_t)(uintptr_t)src;
    unsigned bank,part;
    if(size==PART_STRIDE && part_address(d,&bank,&part)) {
        if(s==BANK_BASE+bank*BANK_STRIDE+0x9504a+part*PART_STRIDE) {
            eul_part_restore(bank,part);
        } else if(s==0x460c8122u || s==0x460bf218u) {
            unsigned which=s==0x460bf218u;
            unsigned kind=U32(which?0x460c80f0u:0x460d0ffau);
            if(kind==17) {
                if(eul_clip_valid[which]) eul_publish_part(bank,part,eul_clips[which]);
                else {
                    EulParams defaults[EUL_LANES],zero={0};
                    for(unsigned l=0;l<EUL_LANES;++l) defaults[l]=zero;
                    eul_publish_part(bank,part,defaults);
                }
                eul_dirty[bank]=1;
            }
        }
    }
    return result;
}
/* Mark native Part and bank dirty so the usual background save includes it. */
static void changed(unsigned bank,unsigned part,unsigned lane) {
    U8(BANK_BASE+BANK_STRIDE*bank+0x95048u)|=(uint8_t)(1u<<part);
    U8(0x100b145eu)|=(uint8_t)(1u<<part);
    eul_dirty[bank]=1;
    if(lane<EUL_LANES) eul_nv_touch_lane(bank,part,lane);
    else eul_nv_touch_part(bank,part);
    eul_schedule(bank);
}
/* Bulk update entry, also exercised by the power-up/card verifier. A caller
 * that changes several lanes must retain the entire Part, not the UI lane. */
void eul_changed(unsigned bank,unsigned part) {
    changed(bank,part,EUL_LANES);
}
