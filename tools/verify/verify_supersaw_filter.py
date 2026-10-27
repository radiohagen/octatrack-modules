#!/usr/bin/env python3
"""Production 22.05 kHz SEM response against its independent TPT transfer function.

Low-level sine probes exclude clipping. This no longer claims response identity
with the full-rate Spectrum DSP: the production filter has a 9 kHz ceiling and
is followed by the oscillator's existing 2x interpolation stage.
"""
from pathlib import Path
import ctypes,json,math,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
class State(ctypes.Structure):
    _fields_=[(n,ctypes.c_int32) for n in ('s0','s1','a1','a2','a3','damping')]+[('envelope',ctypes.c_uint32),('stamp',ctypes.c_uint32),('wet',ctypes.c_uint16),('type',ctypes.c_uint8),('ready',ctypes.c_uint8)]
class Params(ctypes.Structure):
    _fields_=[(n,ctypes.c_uint8) for n in ('cutoff','resonance','amount','decay','type')]
def main():
    out=ROOT/'out/supersaw-filter';out.mkdir(parents=True,exist_ok=True)
    results=[]
    with tempfile.TemporaryDirectory() as tmp:
        c,lib=Path(tmp)/'core.c',Path(tmp)/'core.dylib'
        c.write_text('#define SS_HOST_TEST\n#include "modules/supersaw/adapter.c"\n'
                     'void probe(struct ss_filter *s,const struct ss_filter_params *p,int16_t *a) {ss_filter_half(s,p,1,a,16);}\n')
        subprocess.run(['cc','-O2','-shared','-fPIC','-I',str(ROOT),str(c),'-o',str(lib)],check=True)
        core=ctypes.CDLL(str(lib));core.probe.argtypes=[ctypes.POINTER(State),ctypes.POINTER(Params),ctypes.POINTER(ctypes.c_int16)]
        for cut in (0,32,64,96,127):
            fc=min(9000,60*250**(cut/128));g=math.tan(math.pi*fc/22050)
            for res in (0,64,127):
                k=(.998-res*.587/128)**4
                for hz in (fc/2,fc,min(fc*2,10000)):
                    samples=[round(100*math.sin(2*math.pi*hz*i/22050)) for i in range(16384)]
                    for typ in (1,2,3):
                        p=Params(cut,res,0,64,typ);state=State();actual=[]
                        for i in range(0,len(samples),16):
                            a=(ctypes.c_int16*16)(*samples[i:i+16]);core.probe(ctypes.byref(state),ctypes.byref(p),a);actual.extend(a)
                        def magnitude(x):
                            seg=x[8192:];return abs(sum(v*complex(math.cos(2*math.pi*hz*i/22050),math.sin(2*math.pi*hz*i/22050)) for i,v in enumerate(seg)))
                        omega=1j*math.tan(math.pi*hz/22050)/g
                        h=(1 if typ==1 else omega if typ==2 else omega**2)/(1+k*omega+omega**2)
                        db=20*math.log10(magnitude(actual)/magnitude(samples)/abs(h))
                        # Quantization dominates very quiet stopbands; measure
                        # gain in the useful pass/transition band only.
                        if abs(h)>=.05:assert abs(db)<.7,(cut,res,typ,hz,db)
                        results.append(dict(cutoff=cut,resonance=res,type=typ,hz=hz,ideal_gain=abs(h),error_db=db))
    receipt=dict(result='pass',probes=results,sample_rate=22050,cutoff_ceiling_hz=9000,
                 max_passband_error_db=max(abs(x['error_db']) for x in results if x['ideal_gain']>=.05),
                 scope='Production source-rate filter; analytical steady response, not old full-rate audio identity or hardware acceptance')
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(f'[ok] {len(results)} production SEM response probes; max passband error {receipt["max_passband_error_db"]:.3f} dB')
if __name__=='__main__':main()
