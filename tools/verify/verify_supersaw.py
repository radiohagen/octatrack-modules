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
    old = runpy.run_path(str(ROOT/'modules/sophie/bridge.py'))['assembly']
    new = runpy.run_path(str(ROOT/'modules/supersaw/bridge.py'))['assembly']
    for modules in ({}, {'SOPHIE':None}): assert new(modules) == old(modules)
    for modules in ({'SUPERSAW':None}, {'SUPERSAW':None,'SOPHIE':None}):
        src = new(modules)
        for hook in ('begin','fill','page'): assert src.count('jsr ss_'+hook+'_hook') == 1
        assert src.count('jsr sf_fill_hook') == int('SOPHIE' in modules)
        if 'SOPHIE' in modules:
            assert src.index('jsr sf_fill_hook') < src.index('lea ss_active', src.index('jsr sf_fill_hook')) < src.index('jsr ss_fill_hook')
    module = registry.modules()['SUPERSAW']
    assert not (module.detours or module.pokes or module.symbol_refs or module.cf_patches)
    with tempfile.TemporaryDirectory() as temp:
        exe, raw = Path(temp)/'test', Path(temp)/'neutral.pcm'
        subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror',
                        '-fsanitize=address,undefined','modules/supersaw/test_engine.c',
                        '-o',str(exe)],cwd=ROOT,check=True)
        subprocess.run([str(exe),str(raw)],check=True)
        pcm = array.array('h',raw.read_bytes())
        increment = 21426141
        harmonics = 1
        while harmonics < 128 and increment*2*harmonics*2 < 2**31: harmonics *= 2
        # Independent analytical Fourier series at the actual phase; no engine tables.
        def exact(n):
            return -20000/math.pi * sum(math.sin(2*math.pi*k*((n*increment)%2**32)/2**32)/k
                         for k in range(1,harmonics+1))
        # Independent half-rate synthesis + causal linear interpolation.
        reference = [exact(n-1) if n % 2 else (exact(max(0,n-2))+exact(n))/2
                     for n in range(len(pcm))]
        error = math.sqrt(sum((a-b)**2 for a,b in zip(pcm,reference))/sum(b*b for b in reference))
        assert error < .035, ('Fourier reference error',error)
        assert abs(sum(pcm)/len(pcm)) < 150
        print(f'[ok] independent Fourier reference relative RMS error {error:.6f}')
    print('[ok] unselected images preserve prior Synth source; no competing native hooks')
if __name__ == '__main__': main()
