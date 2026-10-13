#!/usr/bin/env python3
"""Image gate: Sophie/FM coexistence, both cores, Loopback, page resolution."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
def main():
    project=os.environ.get('OT_PROJECT')
    if not project:
        print('[SKIP] Sophie full firmware: set OT_PROJECT to a local fixture');return
    frozen=ROOT/'out/sophie-frozen';frozen.mkdir(parents=True,exist_ok=True)
    for src,dst in (('out/mainos_bus.bin','candidate.bin'),
                    ('out/platform/runtime/runtime.elf','runtime.elf'),
                    ('out/platform/layout.json','layout.json')):
        shutil.copy2(ROOT/src,frozen/dst)
    for args in (('--track','2'),('--track','6','--case','sequence'),
                 ('--track','2','--case','loopback','--metal','96')):
        subprocess.run([sys.executable,'tools/verify/verify_sophie_port.py','--project',project,*args],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'tools/verify/verify_sophie_page.py'],cwd=ROOT,check=True)
if __name__=='__main__':main()
