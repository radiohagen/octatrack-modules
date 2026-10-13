#!/usr/bin/env python3
"""Pinned upstream and reproducible compiler checks for Sophie."""
from pathlib import Path
import subprocess
import runpy
import tempfile
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import toolpath
from remix import registry
ROOT=Path(__file__).resolve().parents[2]
def main():
    subprocess.run(['python3','modules/sophie/generate.py','--check'],cwd=ROOT,check=True)
    subprocess.run(['make','-C','modules/sophie/upstream','test'],cwd=ROOT,check=True)
    bridge=runpy.run_path(str(ROOT/'modules/sophie/bridge.py'))['assembly']
    base=registry.remix('mattias-bottleservice')
    combined=registry.remix('sophie')
    assert tuple(key for key in combined.modules if key != 'SOPHIE')==base.modules
    assert (combined.fx1,combined.hidden,combined.host_slots,combined.locked,combined.settings)==(base.fx1,base.hidden,base.host_slots,base.locked,base.settings)
    module=registry.modules()['SOPHIE']
    assert not (module.detours or module.pokes or module.symbol_refs or module.cf_patches)
    original=(ROOT/'modules/synth/upstream/synth/poly.s').read_text()
    assert bridge({})==original
    assert bridge({'SOPHIE':None}).count('jsr sf_fill_hook')==1
    with tempfile.TemporaryDirectory() as tmp:
        exe=Path(tmp)/'test_sophie_adapter'
        subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror',
                        'modules/sophie/test_adapter.c','-o',str(exe)],cwd=ROOT,check=True)
        subprocess.run([str(exe)],check=True)
    print('[ok] unselected Synth source unchanged; optional adapter anchors pinned')
if __name__=='__main__':main()
