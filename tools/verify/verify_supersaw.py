#!/usr/bin/env python3
"""Original engine math, sanitizer, selection and optional-hook gate."""
from pathlib import Path
import array
import math
import runpy
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import toolpath
from remix import registry
ROOT = Path(__file__).resolve().parents[2]
def main():
    subprocess.run([sys.executable,'modules/supersaw/generate.py','--check'],cwd=ROOT,check=True)
    new = runpy.run_path(str(ROOT/'modules/supersaw/bridge.py'))['assembly']
    upstream = (ROOT/'modules/synth/upstream/synth/poly.s').read_text()
    assert new({}) == upstream
    src = new({'SUPERSAW': None})
    for hook in ('begin','fill','page','carry'):
        assert src.count('jsr ss_'+hook+'_hook') == 1
    module = registry.modules()['SUPERSAW']
    assert len(module.detours)==5 and not (module.pokes or module.symbol_refs or module.cf_patches)
    with tempfile.TemporaryDirectory() as temp:
        exe, raw = Path(temp)/'test', Path(temp)/'neutral.pcm'
        obj = Path(temp)/'adapter.o'
        subprocess.run(['m68k-elf-as','-mcpu=54455','modules/supersaw/adapter.s','-o',str(obj)],cwd=ROOT,check=True)
        symbols = subprocess.check_output(['m68k-elf-nm',str(obj)],text=True)
        for name in ('ss_active','ss_samples','ss_unsupported','ss_voices','ss_poly_voices','ss_poly_samples','ss_descriptor','ss_lfo_descriptor','ss_page_built','ss_lfo_built'):
            rows = [line.split() for line in symbols.splitlines() if line.split()[-1] == name]
            assert len(rows) == 1 and rows[0][1] in ('d','D'), (name,rows,'loader does not clear .bss')
        subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror',
                        '-fsanitize=address,undefined','modules/supersaw/test_engine.c',
                        '-o',str(exe)],cwd=ROOT,check=True)
        subprocess.run([str(exe),str(raw)],check=True)
        samples = array.array('h',raw.read_bytes())
        assert len(samples) == 8192
        increment = 21426141
        harmonics = 1
        while harmonics < 128 and increment*2*harmonics*2 < 2**31: harmonics *= 2
        # Independent spectral law: fade only the upper half of the safe
        # harmonics in sixteen steps across this octave, retaining the old
        # low-frequency 128-partial cap and the high-frequency fundamental.
        upper = 2**31 / harmonics
        fade = min(16, max(0, math.floor(16*(2*increment*2/upper-1)+.5)))
        upper_weight = 1-fade/16 if harmonics>1 else 1
        for morph,polarity,pcm in ((0,1,samples[:4096]),(127,-1,samples[4096:])):
            # Independent analytical Fourier series at the actual phase; no engine tables.
            def exact(n):
                if n < 0: return 0  # cold causal history
                phase = ((n*increment)%2**32)/2**32
                return -10000/math.pi * sum(
                    (math.sin(2*math.pi*k*phase) + polarity*math.sin(2*math.pi*k*(phase+.25)))/k
                    * (1 if k<=harmonics//2 else upper_weight)
                    for k in range(1,harmonics+1))
            # Independent two-saw sum, half-rate source and causal interpolation.
            reference = [exact(n-3) if n % 2 else
                         (-exact(n-6)+9*exact(n-4)+9*exact(n-2)-exact(n))/16
                         for n in range(len(pcm))]
            error = math.sqrt(sum((a-b)**2 for a,b in zip(pcm,reference))/sum(b*b for b in reference))
            assert error < .035, ('Fourier reference error',error)
            assert abs(sum(pcm)/len(pcm)) < 150
            print(f'[ok] independent Fourier reference MORF={morph} relative RMS error {error:.6f}')
    print('[ok] unselected images preserve prior Synth source; no competing native hooks')
if __name__ == '__main__': main()
