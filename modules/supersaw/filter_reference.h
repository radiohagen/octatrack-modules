/* SPDX-License-Identifier: MIT
 * Scalar S7 filter retained as the bit-exact optimization oracle. */
static int32_t ss_reference_mul(int32_t a,int32_t b) {
    return (int32_t)(((int64_t)a*b)>>14);
}
static void ss_filter_reference(struct ss_filter *s,const struct ss_filter_params *p,
                          uint32_t stamp,int16_t *audio,unsigned n) {
    if (!n) return;
    unsigned type=p->type<=3?p->type:0;
    if (!type && !s->wet) { s->ready=0; s->stamp=stamp; return; }
    if (!s->ready || !s->wet) {
        s->s0=s->s1=0;s->envelope=0;s->ready=1;s->stamp=stamp-1;
    }
    if (s->stamp!=stamp) { s->envelope=1u<<24;s->stamp=stamp; }
    unsigned cutoff=(p->cutoff&127)+(((s->envelope>>12)*(p->amount&127))>>12);
    if(cutoff>127)cutoff=127;
    int32_t g=ss_filter_g[cutoff];
    /* Spectrum: damping=(0.998 - (RES/128)*0.587)^4. */
    int32_t b=16351-((p->resonance&127)*9617)/128;
    int32_t k=ss_reference_mul(b,b);k=ss_reference_mul(k,k);
    int32_t den=16384+ss_reference_mul(k,g)+ss_reference_mul(g,g);
    int32_t a1=268435456/den,a2=g,a3=k+g;
    int32_t d1=(a1-s->a1)/(int)n,d2=(a2-s->a2)/(int)n;
    int32_t d3=(a3-s->a3)/(int)n,dk=(k-s->damping)/(int)n;
    if (!s->wet) { s->a1=a1;s->a2=a2;s->a3=a3;s->damping=k;d1=d2=d3=dk=0; }
    if(type)s->type=(uint8_t)type;
    unsigned fall=ss_filter_decay[p->decay&127];
    for(unsigned i=0;i<n;++i) {
        s->a1+=d1;s->a2+=d2;s->a3+=d3;s->damping+=dk;
        int32_t x=(int32_t)audio[i]*256;
        int32_t hp=ss_limit(ss_reference_mul(x-ss_reference_mul(s->s0,s->a3)-s->s1,s->a1));
        int32_t v=ss_reference_mul(hp,s->a2),bp=ss_limit(s->s0+v);
        s->s0=ss_limit(s->s0+2*v);
        int32_t q=ss_reference_mul(bp,s->a2),lp=ss_limit(s->s1+q);
        s->s1=ss_limit(s->s1+2*q);
        int32_t y=s->type==1?lp:s->type==2?bp:hp;
        if(type) { if(s->wet<128)++s->wet; } else if(s->wet)--s->wet;
        audio[i]=(int16_t)((s->wet==128?y:x+((y-x)*(int32_t)s->wet)/128)>>8);
        uint32_t drop=((s->envelope>>8)*fall)>>8;
        if(s->envelope) s->envelope-=drop?drop:1;
    }
    s->a1=a1;s->a2=a2;s->a3=a3;s->damping=k;
}
