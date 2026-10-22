#!/usr/bin/env python3
"""Compare the CPU SEM's steady response with the actual Spectrum DSP core.

Filter-only sine probes at low level avoid the deliberately bounded nonlinear
range. This is response matching, not a claim of sample-identical DSP/CPU audio.
"""
from pathlib import Path
import ctypes,hashlib,json,math,struct,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import toolpath,send_probe
from remix import registry, audition
class State(ctypes.Structure):
    _fields_=[(n,ctypes.c_int32) for n in ('s0','s1','a1','a2','a3','damping')]+[('envelope',ctypes.c_uint32),('stamp',ctypes.c_uint32),('wet',ctypes.c_uint16),('type',ctypes.c_uint8),('ready',ctypes.c_uint8)]
class Params(ctypes.Structure):
    _fields_=[(n,ctypes.c_uint8) for n in ('cutoff','resonance','amount','decay','type')]
def main():
    out=ROOT/'out/supersaw-filter';out.mkdir(exist_ok=True)
    mem=ROOT/'out/dsp/_audition_spectrum_A.mem';mem.unlink(missing_ok=True)
    audition._ensure_insert_mem(registry.by_name('spectrum'))
    mod=registry.by_name('spectrum');init,proc=send_probe.entry_points(str(mem),mod.menu.fx2_id)
    assert (init,proc)!=send_probe.entry_points(str(mem),registry.by_name('send').menu.fx2_id)
    results=[]
    with tempfile.TemporaryDirectory() as tmp:
        c,lib=Path(tmp)/'core.c',Path(tmp)/'core.dylib'
        c.write_text('#define SS_HOST_TEST\n#include "modules/supersaw/adapter.c"\n')
        subprocess.run(['cc','-O2','-shared','-fPIC','-I',str(ROOT),str(c),'-o',str(lib)],check=True)
        core=ctypes.CDLL(str(lib));core.ss_filter_run.argtypes=[ctypes.POINTER(State),ctypes.POINTER(Params),ctypes.c_uint32,ctypes.POINTER(ctypes.c_int16),ctypes.c_uint]
        for cut,res in ((32,0),(64,64),(96,96)):
            fc=60*250**(cut/128)
            for hz in (fc/2,fc,fc*2):
                samples=[round(400*math.sin(2*math.pi*hz*i/44100)) for i in range(12000)]
                (out/'in.raw').write_bytes(struct.pack('<12000i',*(x*256 for x in samples)))
                for typ,shape in ((1,0),(2,64),(3,127)):
                    p=Params(cut,res,0,64,typ);state=State();actual=[]
                    for i in range(0,len(samples),15):
                        a=(ctypes.c_int16*15)(*samples[i:i+15]);core.ss_filter_run(ctypes.byref(state),ctypes.byref(p),1,a,15);actual.extend(a)
                    knobs=[cut,res,64,0,64,64,1,shape,0,0,0,0]
                    cmd=[str(ROOT/'vendor/dsp56300/build/source/dsp_host/dsp_host'),'-mem',str(mem),'-init',f'{init:x}','-proc',f'{proc:x}','-inst','1','-r7','1','-alloc','0','-inmask','1','-frames','15','-blocks','800','-in',str(out/'in.raw'),'-out',str(out/'dsp.raw'),'-params',','.join(map(str,knobs))]
                    subprocess.run(cmd,cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True)
                    raw=(out/'dsp.raw').read_bytes();dsp=struct.unpack(f'<{len(raw)//4}i',raw)[::2][:12000]
                    def magnitude(x,scale):
                        seg=x[6000:];return abs(sum(v*complex(math.cos(2*math.pi*hz*i/44100),math.sin(2*math.pi*hz*i/44100)) for i,v in enumerate(seg)))/scale
                    db=20*math.log10(magnitude(actual,1)/magnitude(dsp,256))
                    assert abs(db)<.7,(cut,res,typ,hz,db)
                    results.append(dict(cutoff=cut,resonance=res,type=typ,hz=hz,cpu_vs_spectrum_db=db))
    receipt=dict(result='pass',probes=results,max_abs_difference_db=max(abs(x['cpu_vs_spectrum_db']) for x in results),spectrum_source_sha256=hashlib.sha256((ROOT/'modules/spectrum/spectrum.asm').read_bytes()).hexdigest(),dsp_mem_sha256=hashlib.sha256(mem.read_bytes()).hexdigest(),scope='Steady low-level response; distinct fixed-point precision and parameter ramp durations; no exact sound identity claim')
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(f'[ok] {len(results)} CPU SEM vs actual Spectrum DSP probes, max {receipt["max_abs_difference_db"]:.3f} dB difference')
if __name__=='__main__':main()
