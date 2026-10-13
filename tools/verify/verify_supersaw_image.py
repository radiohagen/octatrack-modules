#!/usr/bin/env python3
"""Registered full firmware gate, isolated on generated project copies."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
def main():
    project = os.environ.get('OT_PROJECT')
    if not project:
        print('[SKIP] Supersaw full firmware: set OT_PROJECT to a local fixture'); return
    # This combined gate includes Sophie when selected; keep the module usable
    # without Sophie too. The POC candidate intentionally selects both.
    sys.path.insert(0,str(ROOT/'tools'))
    import toolpath
    from remix import registry
    remix = registry.remix(os.environ.get('REMIX','mattias-supersaw-poc'))
    frozen = ROOT/'out/supersaw-frozen'; frozen.mkdir(parents=True,exist_ok=True)
    for src,dst in (('out/mainos_bus.bin','candidate.bin'),('out/platform/runtime/runtime.elf','runtime.elf'),('out/platform/layout.json','layout.json')):
        shutil.copy2(ROOT/src,frozen/dst)
    cases = [('--mode','fm'),('--mode','fm','--case','sequence'),
             ('--mode','dual','--rich'),('--mode','dual','--case','loopback','--rich')]
    if 'SOPHIE' in remix.modules:
        if os.environ.get('OCTABAM_SYNTH_QUALIFICATION') == 'one-at-a-time':
            print('[LIMIT] Sophie/Supersaw simultaneous playback is not qualified; explicit one-at-a-time release', flush=True)
        else:
            cases.append(('--mode','sophie'))
    for args in cases:
        subprocess.run([sys.executable,'tools/verify/verify_supersaw_port.py','--project',project,*args],cwd=ROOT,check=True)
    if 'SOPHIE' in remix.modules and os.environ.get('OCTABAM_SYNTH_QUALIFICATION') == 'one-at-a-time':
        subprocess.run([sys.executable,'tools/verify/verify_synth_selection_port.py'],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'tools/verify/verify_supersaw_cf.py'],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'tools/verify/verify_supersaw_page.py'],cwd=ROOT,check=True)
if __name__ == '__main__': main()
