// Native dispatch/ABI and native LCD pixels, from the composed image.
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <map>
#include <string>
#include <vector>
#include "machine.h"
#include "mc68k/Musashi/m68k.h"
#include "mc68k/cpuState.h"
extern "C" {
#include "engine.h"
#include "storage.h"
}
static std::vector<uint8_t> read(const char *path) {
    std::ifstream f(path,std::ios::binary);
    return {std::istreambuf_iterator<char>(f),std::istreambuf_iterator<char>()};
}
int main(int argc,char **argv) {
    if(argc!=8) {
        std::fprintf(stderr,"euclid_lfo_probe image runtime base settings-address output-directory encode-address decode-address\n");
        return 2;
    }
    auto image=read(argv[1]),runtime=read(argv[2]);
    if(image.empty()||runtime.empty()) return 2;
    uint32_t base=std::strtoul(argv[3],nullptr,16), bank=std::strtoul(argv[4],nullptr,16);
    ot::Machine m(image);
    for(unsigned i=0;i<runtime.size();++i) m.write8(base+i,runtime[i]);
    auto *cpu=m.getCpuState();
    constexpr uint32_t stack=0x47100000,stop=0x470ff000;
    unsigned peak=0,last_count=0;
    auto run_to=[&](uint32_t pc,uint32_t end) {
        m68k_set_reg(cpu,M68K_REG_PC,pc);
        unsigned count=0;
        while(m.pc()!=end && count++<500000) if(!m.step()) break;
        if(m.pc()!=end) {
            std::fprintf(stderr,"failed at %08x from %08x after %u instructions\n",m.pc(),pc,count);
            return false;
        }
        if(count>peak) peak=count;
        last_count=count;
        return true;
    };
    auto run=[&](uint32_t pc) { return run_to(pc,stop); };
    auto args=[&](unsigned a=0,unsigned b=0) {
        m68k_set_reg(cpu,M68K_REG_SR,0x2700);
        m68k_set_reg(cpu,M68K_REG_SP,stack);
        m.write32(stack,stop); m.write32(stack+4,a); m.write32(stack+8,b);
    };
    // Execute the exact linked ColdFire codec against the independent host
    // fixture. These are codec tests, not STORE or filesystem acceptance.
    auto fixture=read((std::string(argv[5])+"/storage-v1.bin").c_str());
    if(fixture.size()!=EUL_FILE_BYTES) return 2;
    constexpr uint32_t input=0x47010000,decoded=0x47012000,encoded=0x47014000;
    uint32_t encode=std::strtoul(argv[6],nullptr,16),decode=std::strtoul(argv[7],nullptr,16);
    for(unsigned i=0;i<fixture.size();++i) m.write8(input+i,fixture[i]);
    args(decoded,input); m.write32(stack+12,EUL_FILE_BYTES);
    if(!run(decode) || m68k_get_reg(cpu,M68K_REG_D0)!=1) return 1;
    for(unsigned i=0;i<EUL_BANK_BYTES;++i)
        if(m.read8(decoded+i)!=fixture[16+i]) return 1;
    args(encoded,EUL_FILE_BYTES); m.write32(stack+12,decoded);
    if(!run(encode) || m68k_get_reg(cpu,M68K_REG_D0)!=1) return 1;
    for(unsigned i=0;i<EUL_FILE_BYTES;++i)
        if(m.read8(encoded+i)!=fixture[i]) return 1;
    m.write8(input+EUL_FILE_BYTES-1,fixture.back()^1);
    for(unsigned i=0;i<EUL_BANK_BYTES;++i) m.write8(decoded+i,0xa5);
    args(decoded,input); m.write32(stack+12,EUL_FILE_BYTES);
    if(!run(decode) || m68k_get_reg(cpu,M68K_REG_D0)!=0) return 1;
    for(unsigned i=0;i<EUL_BANK_BYTES;++i) if(m.read8(decoded+i)!=0xa5) return 1;
    puts("PASS: composed ColdFire sidecar codec matches independent fixture and refuses corruption without partial output");
    peak=0;
    std::map<std::string,uint32_t> symbols;
    std::ifstream symbol_file(std::string(argv[5])+"/symbols.txt");
    std::string name; uint32_t address;
    while(symbol_file>>name>>std::hex>>address) symbols[name]=address;
    if(!symbols.count("eul_st_partsaved") || !symbols.count("eul_st_partclear") || !symbols.count("eul_ui_style")) return 2;
    if(!symbols.count("eul_label") || !symbols.count("eul_icon")) return 2;
    args(0x47015000,19); if(!run(0x4003be4c)) return 1;
    const char label[]="EUCL";
    for(unsigned b=0;b<sizeof(label);++b) if(m.read8(0x47015000+b)!=(uint8_t)label[b]) return 1;
    args(0x400ba876,0xffffffff); m.write32(stack+12,symbols["eul_label"]);
    if(!run(0x40012f30) || m68k_get_reg(cpu,M68K_REG_D0)>19) return 1;
    uint32_t icon=m.read32(0x400bdf82);
    if(icon!=symbols["eul_icon"] || m.read32(icon)!=17 || m.read32(icon+4)!=9 || m.read32(icon+8)!=1) return 1;
    puts("PASS: native WAVE formatter prints EUCL within its 19-pixel cell and slot 19 has a native-sized non-NULL pictogram");
    EulState states[48]={};
    EulParams p; eul_defaults(&p);
    for(unsigned t=0;t<8;++t) {
        m.write8(0x8000182a+t,0); m.write8(0x80001832+t,0);
        for(unsigned l=0;l<3;++l) {
            m.write8(0x80000510+48*t+0x27+l,1);
            m.write8(0x46c76dc0+68*t+0x41+l,1);
        }
    }
    for(unsigned mode=0;mode<8;++mode) {
        p.mode=mode; p.accents=2; p.boost=127; p.attack=27;
        for(unsigned id=0;id<48;++id)
            for(unsigned b=0;b<sizeof(p);++b) m.write8(bank+sizeof(p)*id+b,((uint8_t *)&p)[b]);
        for(unsigned sample=0;sample<256;++sample) for(unsigned id=0;id<48;++id) {
            unsigned phase=(sample%128)*(EUL_PHASE/128),index=id%24,midi=id/24;
            uint32_t native=(midi?0x46c770e0:0x800010e8)+28*index;
            m.write32(native,phase);
            args(0,index);
            m68k_set_reg(cpu,M68K_REG_A0,native);
            m68k_set_reg(cpu,M68K_REG_D0,phase==0);
            for(unsigned r=2;r<8;++r) m68k_set_reg(cpu,(m68k_register_t)(M68K_REG_D0+r),0x12340000+r);
            for(unsigned r=2;r<7;++r) m68k_set_reg(cpu,(m68k_register_t)(M68K_REG_A0+r),0x43210000+r);
            if(!run(m.read32((midi?0x400d6290:0x400d6210)+19*4))) return 1;
            auto expected=eul_process(&states[id],&p,phase,phase==0,0,id);
            if(m.read32(native+4)!=(uint32_t)expected) {
                std::fprintf(stderr,"mismatch mode=%u lane=%u sample=%u actual=%d expected=%d\n",
                             mode,id,sample,(int)m.read32(native+4),expected); return 1;
            }
            for(unsigned r=2;r<8;++r) if(m68k_get_reg(cpu,(m68k_register_t)(M68K_REG_D0+r))!=0x12340000+r) return 1;
            for(unsigned r=2;r<7;++r) if(m68k_get_reg(cpu,(m68k_register_t)(M68K_REG_A0+r))!=0x43210000+r) return 1;
        }
    }
    std::printf("PASS: 98,304 composed-image audio/MIDI waveform calls match C; both directions, callee registers preserved; peak %u instructions\n",peak);
    // Execute the actual native dispatch -> waveform -> DEP -> destination
    // instruction ranges, not an emulated setter or a copy of their math.
    // Phase/TRIG setup is held at a live gate peak here; this is a routing
    // proof, separate from transport/trigger tests. No native instruction is
    // patched or skipped inside either dispatch/output range.
    auto reg=[&](m68k_register_t r,uint32_t v) { m68k_set_reg(cpu,r,v); };
    unsigned routing_cases=0;
    for(unsigned midi=0;midi<2;++midi) for(unsigned consumer=0;consumer<(midi?1u:2u);++consumer)
        for(unsigned id=0;id<24;++id)
        for(unsigned dest=0;dest<30;++dest)
        for(unsigned negative=0;negative<2;++negative) for(unsigned accent=0;accent<2;++accent)
        for(unsigned depth:{0u,16u,127u}) for(unsigned initial:{0u,64u,127u}) {
            unsigned track=id/3,lane=id%3;
            eul_defaults(&p); p.steps=p.pulses=1; p.mode=EUL_GATE|(negative?EUL_NEGATIVE:0);
            p.attack=0; p.decay=127; p.accents=accent; p.boost=127;
            for(unsigned b=0;b<sizeof(p);++b) m.write8(bank+sizeof(p)*(id+24*midi)+b,((uint8_t *)&p)[b]);
            uint32_t native=(midi?0x46c770e0:0x800010e8)+28*id,target;
            int old;
            if(midi) {
                uint32_t page=0x46c76dc0+68*track,live=0x46c76fe0+32*track;
                target=live+dest;
                m.write8(target,initial); m.write8(live+9+lane,depth);
                old=m.read8(target);
                m.write8(page+0x26+lane,dest); m.write8(page+0x41+lane,0);
                m.write32(native,0);
                args(); m.write32(stack+60,native); m.write32(stack+64,0); m.write32(stack+52,0);
                reg(M68K_REG_D3,19); reg(M68K_REG_D4,0); reg(M68K_REG_D5,lane); reg(M68K_REG_D7,3*track);
                reg(M68K_REG_A2,native); reg(M68K_REG_A3,page+0x29+lane);
                reg(M68K_REG_A4,live+6+lane); reg(M68K_REG_A5,32*track);
                if(!run_to(0x40003f3e,0x40003fca)) return 1;
            } else {
                m.write32(0x800000e0,0);
                // Run stock's EMAC initialization, then enter the dispatch
                // with the same register/stack ABI as its loop body.
                args(); if(!run_to(0x40003b90,0x40003bea)) return 1;
                uint32_t page=0x80000510+48*track,voice=0x80000110+64*track-24;
                target=(dest<12?page:voice)+2*dest;
                m.write16(target,initial*256); m.write16(page+0x12+2*lane,depth*256);
                old=(int16_t)m.read16(target);
                m.write8(page+0x1e +lane,dest); m.write8(page+0x27+lane,0);
                constexpr uint32_t trig=0x47018000;
                m.write8(trig+12,8); m.write8(trig+14,0); m.write8(trig+15,255);
                args(id); reg(M68K_REG_D0,0); reg(M68K_REG_D1,0); reg(M68K_REG_D2,lane); reg(M68K_REG_D7,19);
                reg(M68K_REG_A1,0x400d6210); reg(M68K_REG_A2,page); reg(M68K_REG_A3,native);
                reg(M68K_REG_A5,voice); reg(M68K_REG_A6,trig);
                if(!run_to(consumer?0x4000d012:0x40003c78,consumer?0x4000d07c:0x40003ce2)) return 1;
            }
            int gain=(accent?2:1)*(negative?-1:1),scale=midi?1:256;
            int want=old+gain*(int)(depth==127?128:depth)*scale;
            if(want<0) want=0;
            if(want>127*scale) want=127*scale;
            int got=midi?m.read8(target):m.read16(target);
            if(got!=want || (int32_t)m.read32(native+4)!=gain*(int)EUL_PHASE) {
                std::fprintf(stderr,"native route midi=%u lane=%u dest=%u neg=%u accent=%u depth=%u base=%d got=%d want=%d raw=%d\n",
                    midi,id,dest,negative,accent,depth,old,got,want,(int32_t)m.read32(native+4)); return 1;
            }
            ++routing_cases;
        }
    std::printf("PASS: %u native destination cases: inline/standalone audio and MIDI, all lanes/destinations, POS/NEG, accents, DEP 0/16/127 and clipping\n",routing_cases);
    // Instruction cost, including the expensive first call after edits/Part
    // changes, not just a steady 8-step waveform. These are instruction
    // counts, not a claim about hardware cycles or a DSP-loaded frame deadline.
    unsigned setup_peak=0,steady_peak=0,setup_batch=0,steady_batch=0;
    unsigned cold_peak=0,cold_batch=0;
    if(!symbols.count("eul_context")) return 2;
    for(unsigned mode=0;mode<8;++mode) for(unsigned pulses:{1u,8u,16u}) {
        eul_defaults(&p); p.steps=16; p.pulses=pulses; p.accents=pulses;
        p.mode=mode; p.attack=127; p.decay=127; p.boost=127; p.swing=30;
        for(unsigned id=0;id<48;++id) for(unsigned b=0;b<sizeof(p);++b)
            m.write8(bank+sizeof(p)*id+b,((uint8_t *)&p)[b]);
        unsigned cold_batches[2]={0,0};
        for(unsigned id=0;id<48;++id) {
            // A context mismatch follows the real Part-change cold path,
            // including random-table initialization, without assuming the
            // compiler's private EulState structure packing.
            m.write32(symbols["eul_context"]+4*id,0);
            unsigned midi=id/24,index=id%24;
            uint32_t native=(midi?0x46c770e0:0x800010e8)+28*index;
            m.write32(native,0);
            args(0,index); reg(M68K_REG_A0,native); reg(M68K_REG_D0,1);
            if(!run(m.read32((midi?0x400d6290:0x400d6210)+19*4))) return 1;
            cold_batches[midi]+=last_count;
            if(last_count>cold_peak) cold_peak=last_count;
        }
        for(unsigned batch:cold_batches) if(batch>cold_batch) cold_batch=batch;
        // Change coefficients once more to measure a warm edit separately.
        for(unsigned id=0;id<48;++id) m.write8(bank+sizeof(p)*id+4,126);
        for(unsigned sample=0;sample<64;++sample) {
            unsigned batches[2]={0,0};
            for(unsigned id=0;id<48;++id) {
                unsigned midi=id/24,index=id%24;
                uint32_t native=(midi?0x46c770e0:0x800010e8)+28*index;
                m.write32(native,sample*(EUL_PHASE/64));
                args(0,index); reg(M68K_REG_A0,native); reg(M68K_REG_D0,!sample);
                if(!run(m.read32((midi?0x400d6290:0x400d6210)+19*4))) return 1;
                batches[midi]+=last_count;
                unsigned &maximum=sample?steady_peak:setup_peak;
                if(last_count>maximum) maximum=last_count;
            }
            unsigned &maximum=sample?steady_batch:setup_batch;
            for(unsigned batch:batches) if(batch>maximum) maximum=batch;
        }
    }
    std::printf("COST: 16-step stress: setup/steady peak %u/%u instructions per lane; peak 24-lane batch %u/%u\n",
                setup_peak,steady_peak,setup_batch,steady_batch);
    std::printf("COST: cold Part context peak %u instructions per lane; peak 24-lane batch %u\n",cold_peak,cold_batch);
    // Execute the complete native clock/trigger consumers, not just their
    // waveform dispatch tails. Restore identical native state before SQR and
    // EUCLID calls; only +4/+8 (waveform/held output) may differ afterward.
    // The firmware initializer copies these exact ROM control tables.
    args(); if(!run_to(0x40009062,0x4000908c)) return 1;
    m.write32(0x8000181c,2880); m.write32(0x800000e0,0);
    unsigned clock_cases=0,held_cases=0,terminal_cases=0;
    for(unsigned midi=0;midi<2;++midi) for(unsigned trial=0;trial<4;++trial) {
        uint32_t state_base=midi?0x46c770e0:0x800010e8;
        std::vector<uint8_t> native_state[2]={std::vector<uint8_t>(672),std::vector<uint8_t>(672)};
        for(unsigned id=0;id<24;++id) {
            unsigned phase=(id%3==0?EUL_PHASE/2:EUL_PHASE)-1;
            for(auto &saved:native_state) for(unsigned b=0;b<4;++b) saved[id*28+b]=phase>>(24-8*b);
            eul_defaults(&p); p.steps=16; p.mode=(id+trial)%4; p.accents=2; p.boost=127;
            for(unsigned b=0;b<sizeof(p);++b) m.write8(bank+sizeof(p)*(id+24*midi)+b,((uint8_t *)&p)[b]);
            m.write32(symbols["eul_context"]+4*(id+24*midi),0);
        }
        for(unsigned frame=0;frame<128;++frame) {
            unsigned event=frame==3?8:frame==7?16:frame==11?24:0;
            for(unsigned variant=0;variant<2;++variant) {
                for(unsigned b=0;b<672;++b) m.write8(state_base+b,native_state[variant][b]);
                for(unsigned track=0;track<8;++track) {
                    m.write8(midi?0x46c77380+track:0x80004858+8*track,event);
                    uint32_t page=midi?0x46c76dc0+68*track:0x80000510+48*track;
                    for(unsigned lane=0;lane<3;++lane) {
                        int speed=lane==0?16:lane==1?64:trial&1?-16:0;
                        m.write8(page+(midi?0x29:0x21)+lane,variant?19:4);
                        m.write8(page+(midi?0x41:0x27)+lane,track);
                        m.write8(page+(midi?0x3e:0x24)+lane,lane==1?6:0);
                        m.write8(page+(midi?0x26:0x1e)+lane,18+lane);
                        if(midi) {
                            uint32_t live=0x46c76fe0+32*track;
                            m.write8(live+6+lane,speed); m.write8(live+9+lane,16);
                            m.write8(live+18+lane,64);
                        } else {
                            m.write16(page+12+2*lane,speed*256);
                            m.write16(page+18+2*lane,16*256);
                            m.write16(0x80000110+64*track+12+2*lane,64*256);
                        }
                    }
                }
                args(0); if(!run(midi?0x40003df8:0x40003b90)) return 1;
                if(variant) for(unsigned id=0;id<24;++id) {
                    unsigned trig=id/3;
                    uint32_t native=state_base+28*id,phase=m.read32(native);
                    if(trig==2 && !event) {
                        for(unsigned b=8;b<12;++b) if(m.read8(native+b)!=native_state[1][28*id+b]) {
                            std::fprintf(stderr,"HOLD changed without event midi=%u frame=%u lane=%u\n",midi,frame,id); return 1;
                        }
                        ++held_cases;
                    }
                    if(((trig==4 || trig==7) && phase>=EUL_PHASE/2) || phase>=EUL_PHASE) {
                        if(m.read32(native+4)) { std::fprintf(stderr,"nonzero terminal midi=%u trig=%u phase=%x\n",midi,trig,phase); return 1; }
                        ++terminal_cases;
                    }
                }
                for(unsigned b=0;b<672;++b) native_state[variant][b]=m.read8(state_base+b);
            }
            for(unsigned id=0;id<24;++id) for(unsigned b=0;b<28;++b) {
                if(b>=4 && b<12) continue;
                if(native_state[0][28*id+b]!=native_state[1][28*id+b]) {
                    std::fprintf(stderr,"native clock differs midi=%u trial=%u frame=%u lane=%u byte=%u\n",midi,trial,frame,id,b); return 1;
                }
            }
            clock_cases+=24;
        }
    }
    if(!held_cases || !terminal_cases) return 1;
    std::printf("PASS: %u complete native audio/MIDI clock cases match stock phase/state across eight TRIG modes, note/sync events, MULT and positive/zero/reverse speed; %u HOLD and %u terminal checks\n",clock_cases,held_cases,terminal_cases);
    // Exercise all three installed detours, including the ISR's inline copy.
    // Check the displaced instructions and live registers, not only C math.
    unsigned step_clock_cases=0;
    for(unsigned site=0;site<3;++site) for(unsigned steps=1;steps<=16;++steps)
    for(unsigned id=0;id<24;++id) for(unsigned wave=0;wave<20;++wave) {
        unsigned midi=site==2, identity=id+24*midi;
        m.write8(bank+sizeof(p)*identity,steps);
        m.write32(symbols["eul_clock_context"]+4*identity,0);
        int32_t remainder=0;
        for(int sign=-1;sign<=1;++sign) {
            int32_t increment=sign*12347, expected=increment;
            if(wave==19) expected=eul_clock(increment,steps,&remainder);
            args(id); m.write32(stack+68,increment);
            constexpr uint32_t state=0x47018000;
            m.write32(state,1000000);
            for(unsigned r=1;r<8;++r) reg((m68k_register_t)(M68K_REG_D0+r),0x12340000+r);
            for(unsigned r=0;r<7;++r) reg((m68k_register_t)(M68K_REG_A0+r),0x23450000+r);
            reg(M68K_REG_D0,increment);
            if(midi) { reg(M68K_REG_D3,0x80000000|wave); reg(M68K_REG_D5,id%3); reg(M68K_REG_D7,id/3*3); reg(M68K_REG_A2,state); }
            else { reg(M68K_REG_D7,wave); reg(M68K_REG_A3,state); }
            unsigned saved[15];
            for(unsigned r=0;r<15;++r) saved[r]=m68k_get_reg(cpu,(m68k_register_t)(M68K_REG_D1+r));
            uint32_t start=site==0?0x40003c4a:site==1?0x4000cfe4:0x40003eec;
            uint32_t end=site==0?0x40003c50:site==1?0x4000cfea:0x40003ef2;
            if(!run_to(start,end)) return 1;
            if((int32_t)m68k_get_reg(cpu,M68K_REG_D0)!=expected+(midi?1000000:0)
                || (int32_t)m.read32(stack+(midi?68:0))!=expected) {
                std::fprintf(stderr,"step clock site=%u steps=%u lane=%u wave=%u sign=%d\n",site,steps,id,wave,sign); return 1;
            }
            for(unsigned r=0;r<15;++r) if(saved[r]!=m68k_get_reg(cpu,(m68k_register_t)(M68K_REG_D1+r))) return 1;
            if(!midi && m.read32(state+24)!=0x12340006) return 1;
            ++step_clock_cases;
        }
    }
    std::printf("PASS: %u installed fixed-step clock cases: 1-16 steps, all lanes, positive/zero/reverse, all stock waveforms bypass, all live registers preserved\n",step_clock_cases);
    // Independent full native-clock oracle: compare the accumulated stock
    // increment with a seven-step FREE, ONE and HALF clock. No phase pokes
    // between frames, and no calls directly to the new scaling helper.
    for(unsigned midi=0;midi<2;++midi) {
        uint32_t state_base=midi?0x46c770e0:0x800010e8;
        std::vector<uint8_t> saved[2]={std::vector<uint8_t>(672),std::vector<uint8_t>(672)};
        uint64_t total=0; unsigned old_stock=0,ends=0;
        for(unsigned frame=0;frame<6000;++frame) {
            for(unsigned variant=0;variant<2;++variant) {
                for(unsigned b=0;b<672;++b) m.write8(state_base+b,saved[variant][b]);
                for(unsigned track=0;track<8;++track) {
                    m.write8(midi?0x46c77380+track:0x80004858+8*track,0);
                    uint32_t page=midi?0x46c76dc0+68*track:0x80000510+48*track;
                    for(unsigned lane=0;lane<3;++lane) {
                        unsigned id=track*3+lane,identity=id+24*midi;
                        m.write8(bank+sizeof(p)*identity,7);
                        if(!frame) m.write32(symbols["eul_clock_context"]+4*identity,0);
                        m.write8(page+(midi?0x29:0x21)+lane,variant?19:4);
                        m.write8(page+(midi?0x41:0x27)+lane,variant?(lane==0?0:lane==1?3:4):0);
                        m.write8(page+(midi?0x3e:0x24)+lane,1);
                        if(midi) m.write8(0x46c76fe0+32*track+6+lane,64);
                        else m.write16(page+12+2*lane,64*256);
                    }
                }
                args(0); if(!run(midi?0x40003df8:0x40003b90)) return 1;
                if(!variant) {
                    unsigned phase=m.read32(state_base);
                    total+=(phase-old_stock)&(EUL_PHASE-1); old_stock=phase;
                } else for(unsigned id=0;id<24;++id) {
                    uint64_t scaled=total*16/7;
                    unsigned limit=id%3==1?EUL_PHASE:EUL_PHASE/2;
                    unsigned expected=id%3==0?scaled&(EUL_PHASE-1):scaled>=limit?limit:(unsigned)scaled;
                    unsigned got=m.read32(state_base+28*id);
                    if(got!=expected) {
                        std::fprintf(stderr,"seven-step native clock midi=%u frame=%u lane=%u got=%x expected=%x\n",midi,frame,id,got,expected); return 1;
                    }
                    if(id%3 && scaled>=limit) ++ends;
                }
                for(unsigned b=0;b<672;++b) saved[variant][b]=m.read8(state_base+b);
            }
        }
        if(!ends) return 1;
    }
    puts("PASS: complete native audio/MIDI seven-step FREE/ONE/HALF clocks match independent accumulated-increment oracle for 6000 frames");
    // Use the real SETUP drawer and font, on a correctly shaped native surface.
    constexpr uint32_t window=0x47000000,plane=0x47001000;
    m.write32(0x400bc038,window);
    m.write32(0x400bc05c,0x400572e8);
    m.write32(window+36,115); m.write32(window+40,64); m.write32(window+44,2);
    m.write32(window+48,plane); m.write32(window+52,plane+1024);
    m.write32(0x46c82456,0x400e21e0);
    m.write8(0x80000002,0); m.write8(0x100b14cf,0); m.write8(0x100b14cc,0);
    m.write32(0x460d1a32,0); m.write32(0x80000012,0);
    m.write8(0x400e21e0+0x8ed80+0x2f5,19);
    m.write8(0x400e21e0+0x8ed80+0x11a,64);
    m.write8(0x400e21e0+0x8ed80+0x30a,1);
    eul_defaults(&p); p.steps=16; p.pulses=5; p.accents=2;
    for(unsigned b=0;b<sizeof(p);++b) m.write8(bank+b,((uint8_t *)&p)[b]);
    auto screenshot=[&](const std::string &label) {
        std::ofstream out(std::string(argv[5])+"/"+label+".ppm",std::ios::binary);
        out<<"P6\n115 64\n255\n";
        for(unsigned y=0;y<64;++y) for(unsigned x=0;x<115;++x) {
            unsigned col=63-y;
            unsigned v=m.read8(plane+x*8+col/8);
            unsigned char c=(v&(128>>(col%8)))?0:255;
            out.write((const char *)&c,1); out.write((const char *)&c,1); out.write((const char *)&c,1);
        }
    };
    for(unsigned style=0;style<2;++style) {
        m.write32(symbols.at("eul_ui_style"),style);
        for(unsigned page=0;page<2;++page) {
            args(0x31,1);
            if(!run(m.read32(0x400bbb56))) return 1;
            screenshot("style"+std::to_string(style)+"-page"+std::to_string(page));
            std::vector<uint8_t> before(2048);
            for(unsigned b=0;b<2048;++b) before[b]=m.read8(plane+b);
            args(); if(!run(0x400572e8)) return 1;
            for(unsigned b=0;b<2048;++b) if(before[b]!=m.read8(plane+b)) {
                std::fprintf(stderr,"non-idempotent redraw style=%u page=%u plane-byte=%u before=%02x after=%02x\n",style,page,b,before[b],m.read8(plane+b)); return 1;
            }
        }
    }
    m.write32(symbols.at("eul_ui_style"),0);
    args(0x32,1); if(!run(m.read32(0x400bbb70))) return 1;
    screenshot("stock-lfo-setup");
    args(0x31,1); if(!run(m.read32(0x400bbb56))) return 1;
    puts("PASS: two six-control UI designs and native LFO SETUP rendered with firmware font, knob widgets and chrome; repeated redraws are byte-identical in both planes");
    // Check both layouts at their limits, including mode-specific labels.
    // Native windows have one ink plane and one opacity mask, not grey levels.
    for(unsigned style=0;style<2;++style) for(unsigned midi=0;midi<2;++midi)
        for(unsigned mode=0;mode<4;++mode) for(unsigned hi=0;hi<2;++hi) {
            m.write32(symbols.at("eul_ui_style"),style);
            m.write32(0x80000012,midi);
            m.write8(0x400e21e0+0x8ed80+(midi?0x4eb:0x2f5),19);
            m.write8(0x400e21e0+0x8ed80+(midi?0x3e8:0x11a),hi?96:8);
            m.write8(0x400e21e0+0x8ed80+(midi?0x500:0x30a),hi?3:0);
            eul_defaults(&p);
            p.steps=hi?16:1; p.pulses=hi?16:0; p.rotate=hi?15:0;
            p.mode=mode|(hi?EUL_NEGATIVE:0); p.attack=hi?127:0; p.decay=hi?127:0;
            p.accents=hi?16:0; p.accent_rotate=hi?15:0;
            p.boost=hi?127:0; p.swing=hi?30:0;
            uint32_t settings=bank+sizeof(p)*24*midi;
            for(unsigned b=0;b<sizeof(p);++b) m.write8(settings+b,((uint8_t *)&p)[b]);
            // Protect the unused tail of both 1-bpp planes against overflow.
            for(unsigned mask=0;mask<2;++mask) for(unsigned b=920;b<1024;++b)
                m.write8(plane+1024*mask+b,0xa5);
            m.write32(symbols.at("eul_editing"),0);
            for(unsigned page=0;page<2;++page) {
                args(0x31,1); if(!run(m.read32(0x400bbb56))) return 1;
                screenshot("style"+std::to_string(style)+(midi?"-midi":"-audio")+
                    "-mode"+std::to_string(mode)+(hi?"-max":"-min")+"-page"+std::to_string(page));
                for(unsigned mask=0;mask<2;++mask) for(unsigned b=920;b<1024;++b)
                    if(m.read8(plane+1024*mask+b)!=0xa5) {
                        std::fprintf(stderr,"LCD plane overflow: style=%u mode=%u page=%u\n",style,mode,page);
                        return 1;
                    }
            }
        }
    m.write32(symbols.at("eul_ui_style"),0);
    m.write32(0x80000012,0);
    // No intervening redraw: YES must repin the now-selected audio lane.
    args(0x31,1); if(!run(m.read32(0x400bbb56))) return 1;
    if(m.read32(symbols.at("eul_editing"))!=1 || m.read32(symbols.at("eul_page"))!=0) return 1;
    puts("PASS: 64 extrema/mode/audio/MIDI layout renders stay inside both native planes; YES repins a changed selection");
    // Register the actual setup keymap; test the native dispatch path, not
    // merely the C setter. Held encoder-push state must not multiply delta.
    args(0x400bbd22); if(!run(0x40031494)) return 1;
    for(unsigned midi=0;midi<2;++midi) {
        if(midi) {
            m.write32(0x80000012,1);
            m.write8(0x400e21e0+0x8ed80+0x4eb,19);
            // First redraw invalidates the old, audio-pinned editor.
            args(); if(!run(0x400572e8)) return 1;
            args(0x31,1); if(!run(m.read32(0x400bbb56))) return 1;
        } else {
            args(0x34,1); if(!run(m.read32(0x400bbb22))) return 1;
        }
        uint32_t settings=bank+sizeof(p)*24*midi;
        eul_defaults(&p);
        for(unsigned b=0;b<sizeof(p);++b) m.write8(settings+b,((uint8_t *)&p)[b]);
        const unsigned page0[]={0,1,2,6,7,8},page1[]={3,4,5,9};
        for(unsigned enc=0;enc<6;++enc) {
            unsigned field=page0[enc],old=m.read8(settings+field);
            m.write32(0x46c7d8ee + (0x38+enc)*24,1);
            args(enc,1); if(!run(0x40031944)) return 1;
            if(m.read8(settings+field)!=old+1) {
                std::fprintf(stderr,"encoder %u midi=%u: +1 became %d\n",enc,midi,
                             (int)m.read8(settings+field)-(int)old); return 1;
            }
            args(enc,-1); if(!run(0x40031944)) return 1;
            if(m.read8(settings+field)!=old) return 1;
        }
        args(0x31,1); if(!run(m.read32(0x400bbb56))) return 1;
        for(unsigned enc=0;enc<4;++enc) {
            unsigned field=page1[enc],old=m.read8(settings+field);
            args(enc,1); if(!run(0x40031944)) return 1;
            if(m.read8(settings+field)!=old+1) return 1;
        }
        args(6,127); if(!run(0x40031944)) return 1;
        if(m.read8(settings)!=8) return 1;
        args(4,1); if(!run(0x40031944)) return 1;
        if(m.read8(settings+3)!=(EUL_GATE|EUL_NEGATIVE)) return 1;
        args(4,1); if(!run(0x40031944)) return 1;
        if(m.read8(settings+3)!=(EUL_GATE|EUL_NEGATIVE)) return 1;
        args(4,-1); if(!run(0x40031944)) return 1;
        if(m.read8(settings+3)!=EUL_GATE) return 1;
        // RATE's native descriptor/Part writer needs a complete boot. Its
        // preset/STOP/pushed controls are covered by the panel gate.
        // LEVEL never edits this page. DEC/LEN is inactive for RAND/LOOP.
        for(unsigned enc=6;enc<7;++enc) {
            std::vector<uint8_t> before;
            for(unsigned b=0;b<sizeof(p);++b) before.push_back(m.read8(settings+b));
            args(enc,127); if(!run(0x40031944)) return 1;
            for(unsigned b=0;b<sizeof(p);++b) if(m.read8(settings+b)!=before[b]) return 1;
        }
        for(unsigned mode=EUL_RAND;mode<=EUL_LOOP;++mode) {
            m.write8(settings+3,mode);
            unsigned old=m.read8(settings+5);
            args(2,127); if(!run(0x40031944)) return 1;
            args(2,-127); if(!run(0x40031944)) return 1;
            if(m.read8(settings+5)!=old) return 1;
        }
        m.write8(settings+3,EUL_GATE);
        // NO returns to native setup without discarding edits.
        args(0x32,1); if(!run(m.read32(0x400bbb70))) return 1;
        if(m.read8(settings+9)!=1 || m.read8(settings+3)!=EUL_GATE) return 1;
    }
    puts("PASS: native keymap and encoder dispatch: audio/MIDI, 11 pattern controls, signed unit steps, held pushes, DIR end stops, inactive controls inert, NO retains edits; RATE uses the full-boot panel gate");
    // STORE's actual client ABI, then Part Reload's installed copy adapter.
    // No file I/O is replaced or claimed by this direct-memory probe.
    for(unsigned part=0;part<4;++part) {
        for(unsigned id=0;id<48;++id) {
            eul_defaults(&p); p.rotate=(id+part)%8; p.accents=(id+part)%4;
            for(unsigned b=0;b<sizeof(p);++b)
                m.write8(bank+(part*48+id)*sizeof(p)+b,((uint8_t *)&p)[b]);
        }
        args(); m68k_set_reg(cpu,M68K_REG_D0,part);
        if(!run(symbols.at("eul_st_partsaved"))) return 1;
        for(unsigned b=0;b<480;++b) {
            if(m.read8(bank+part*480+b)!=m.read8(bank+(part+4)*480+b)) return 1;
            m.write8(bank+part*480+b,0);
        }
        uint32_t native_work=0x400e21e0+0x8ed80+part*0x18b2;
        uint32_t native_saved=0x400e21e0+0x9504a+part*0x18b2;
        for(unsigned b=0;b<0x18b2;++b) m.write8(native_saved+b,(b+part)&255);
        args(native_work,native_saved); m.write32(stack+12,0x18b2);
        if(!run(m.read32(0x4004ab04))) return 1;
        for(unsigned b=0;b<0x18b2;++b)
            if(m.read8(native_work+b)!=m.read8(native_saved+b)) return 1;
        for(unsigned b=0;b<480;++b)
            if(m.read8(bank+part*480+b)!=m.read8(bank+(part+4)*480+b)) return 1;
        args(); m68k_set_reg(cpu,M68K_REG_D0,part);
        if(!run(symbols.at("eul_st_partclear"))) return 1;
        for(unsigned b=0;b<480;++b)
            if(m.read8(bank+part*480+b) || m.read8(bank+(part+4)*480+b)) return 1;
    }
    puts("PASS: installed ColdFire Part Save/Clear callbacks and scoped Part Reload copy preserve native bytes and all 48 lanes");
    // Full native Part clipboard capture/paste and undo-capture/paste routines.
    // Use a non-playing destination Part to avoid claiming native apply here.
    constexpr unsigned source_bank=1,dest_bank=2,source_part=2,dest_part=3;
    uint32_t source_part_data=bank+source_bank*3840+source_part*480;
    uint32_t dest_part_data=bank+dest_bank*3840+dest_part*480;
    std::vector<uint8_t> expected_part(480);
    for(unsigned lane=0;lane<48;++lane) {
        eul_defaults(&p); p.rotate=lane%8; p.accents=lane%4; p.boost=lane+1;
        for(unsigned b=0;b<sizeof(p);++b) {
            uint8_t value=((uint8_t *)&p)[b];
            expected_part[lane*sizeof(p)+b]=value;
            m.write8(source_part_data+lane*sizeof(p)+b,value);
        }
    }
    m.write32(0x46c82456,0x400e21e0+source_bank*0x9b340);
    args(source_part); if(!run(0x4002932c)) return 1;
    if(m.read32(0x460d0ffa)!=17) return 1;
    // Change the source after capture; paste must use the captured snapshot.
    for(unsigned b=0;b<480;++b) m.write8(source_part_data+b,0);
    m.write32(0x46c82456,0x400e21e0+dest_bank*0x9b340);
    m.write8(0x80000002,dest_bank); m.write8(0x80000003,0);
    args(dest_part); if(!run(0x40029b78)) return 1;
    for(unsigned b=0;b<480;++b) if(m.read8(dest_part_data+b)!=expected_part[b]) return 1;
    args(0,dest_part); if(!run(0x400292a0)) return 1;
    if(m.read32(0x460c80f0)!=17) return 1;
    for(unsigned b=0;b<480;++b) m.write8(dest_part_data+b,0);
    args(0x460bf218,dest_part); if(!run(0x40029a4c)) return 1;
    for(unsigned b=0;b<480;++b) if(m.read8(dest_part_data+b)!=expected_part[b]) return 1;
    // Wrong native kind must not revive an old Euclid mirror.
    m.write32(0x460d0ffa,1);
    for(unsigned b=0;b<480;++b) m.write8(dest_part_data+b,0);
    args(dest_part); if(!run(0x40029b78)) return 1;
    for(unsigned b=0;b<480;++b) if(m.read8(dest_part_data+b)) return 1;
    puts("PASS: native Part copy/paste across banks, immutable clipboard snapshot, undo mirror restore, and clipboard-kind rejection");
    return 0;
}
