/* SPDX-License-Identifier: MIT
 * Setup uses the otherwise unused NEIGHBOR setup row in this FLEX Part.
 * This leaves FLEX's LOOP/SLIC/TSTR transport bytes intact. The last byte
 * tags the row; the native validator wrapper preserves only tagged rows.
 */
#define SS_ROW (0x1da+18)
#define SS_TAG 83
static uint8_t *ss_part(void) {
    uint32_t bank=*(volatile uint32_t *)0x46c82456u;
    unsigned part=*(volatile uint8_t *)0x100b14cfu;
    return bank>=0x40000000u && bank<0x48000000u && part<4 ?
        (uint8_t *)(uintptr_t)(bank+0x8ed80+6322*part):0;
}
static void ss_store(uint8_t *part,unsigned at,uint8_t value) {
    part[at]=value;
    unsigned p=*(volatile uint8_t *)0x100b14cfu;
    *(volatile uint8_t *)(uintptr_t)(0x100a4eceu+6322*p+at)=value;
    uint8_t *bank=(uint8_t *)(uintptr_t)*(volatile uint32_t *)0x46c82456u;
    bank[0x95048]|=(uint8_t)(1u<<p);
    *(volatile uint8_t *)0x100b145eu|=(uint8_t)(1u<<p);
    *(volatile uint32_t *)(bank+0x9b332)=1;
    *(volatile uint32_t *)0x100f8598u=1;
}
void ss_config(unsigned track) {
    uint8_t *part=ss_part();if(!part || track>=8)return;
    unsigned at=SS_ROW+30*track;
    if(part[at+5]!=SS_TAG) {
        uint8_t fine=part[0x30+30*track+3]&127;
        const uint8_t defaults[6]={fine,0,0,64,0,SS_TAG};
        for(unsigned i=0;i<6;++i)ss_store(part,at+i,defaults[i]);
        ss_store(part,0x30+30*track+3,127);
        *(volatile uint8_t *)(uintptr_t)(0x80000810u+72*track+3)=127;
    }
    #pragma GCC unroll 6
    for(unsigned i=0;i<6;++i)ss_setup[track][i]=part[at+i]&127;
    /* MIDI/key polyphony only: no shape expansion or recorded chord locks. */
    *(volatile uint8_t *)(uintptr_t)(0x80000810u+72*track+11)=0;
}
unsigned ss_fine(unsigned track,unsigned original) {
    if(track>=8 || !ss_active[track])return original;
    ss_config(track);return (unsigned)ss_setup[track][0]<<8;
}
void ss_fine_fmt(char *out,int value) {
    int v=(value&127)-64;
    if(v<0){*out++='-';v=-v;}else if(v)*out++='+';
    if(v>=10)*out++=(char)('0'+v/10);
    *out++=(char)('0'+v%10);*out++='c';*out=0;
}
void ss_type_fmt(char *out,int value) {
    const char *name=value==1?"LOW":value==2?"BP":value==3?"HP":"OFF";
    do { *out++=*name; } while(*name++);
}
unsigned ss_setup_row(unsigned row,unsigned track) {
    return row==1 && ss_assigned(track) ? 3:row;
}
uint8_t *ss_setup_page(uint8_t *original,unsigned track,unsigned row) {
    return row==1 ? ss_page(original,track):original;
}
int ss_setup_edit(unsigned slot,int delta) {
    unsigned track=*(volatile uint8_t *)0x80000000u;
    if(*(volatile uint32_t *)0x460d5c30u!=1 || !ss_assigned(track))return 0;
    if(slot>=5)return slot==5;
    ss_config(track);
    /* A selector advances one position even with the encoder held down. */
    if(slot==4)delta=(delta>0)-(delta<0);
    else if(*(volatile uint32_t *)(uintptr_t)(0x46c7d8eeu+24*(slot+56)))delta*=7;
    int value=ss_setup[track][slot]+delta,max=slot==4?3:127;
    if(value<0)value=0;
    if(value>max)value=max;
    ss_store(ss_part(),SS_ROW+30*track+slot,(uint8_t)value);
    ss_setup[track][slot]=(uint8_t)value;
    return 1;
}
#ifdef SS_HOST_TEST
static int ss_stock_validate(void *part) { (void)part;return 0; }
#else
extern int ss_stock_validate(void *part);
#endif
int ss_validate(void *ptr) {
    uint8_t *part=ptr,saved[8][6];unsigned mask=0;

    for(unsigned t=0;t<8;++t)if(part[0x22+t]==1 && part[SS_ROW+30*t+5]==SS_TAG) {
        mask|=1u<<t;
        for(unsigned i=0;i<6;++i){saved[t][i]=part[SS_ROW+30*t+i];part[SS_ROW+30*t+i]=0;}
    }
    int result=ss_stock_validate(part);
    for(unsigned t=0;t<8;++t)if(mask&(1u<<t))
        for(unsigned i=0;i<6;++i)part[SS_ROW+30*t+i]=saved[t][i]&127;
    return result;
}
