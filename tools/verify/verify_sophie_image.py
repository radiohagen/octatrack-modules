#!/usr/bin/env python3
"""Image gate: Sophie/FM coexistence, both cores, Loopback, page resolution."""
from pathlib import Path
import hashlib
import json
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
    identities={}
    for src,dst in (('out/mainos_bus.bin','candidate.bin'),
                    ('out/platform/runtime/runtime.elf','runtime.elf'),
                    ('out/platform/layout.json','layout.json')):
        shutil.copy2(ROOT/src,frozen/dst)
        identities[src]=hashlib.sha256((frozen/dst).read_bytes()).hexdigest()
    def unchanged():
        for src,expected in identities.items():
            assert hashlib.sha256((ROOT/src).read_bytes()).hexdigest()==expected, \
                f'Sophie image inputs changed during verification: {src}'
    unchanged()
    for args in (('--track','2'),('--track','6','--case','sequence'),
                 ('--track','2','--case','loopback','--metal','96'),
                 ('--track','2','--fine','-32','--no-harmony'),
                 ('--track','2','--fine','32','--no-harmony')):
        subprocess.run([sys.executable,'tools/verify/verify_sophie_port.py','--project',project,*args],cwd=ROOT,check=True)
        unchanged()
        options=dict(zip(args[::2],args[1::2]))
        track=options['--track'];case=options.get('--case','midi-mono')
        metal=options.get('--metal','0');fine=options.get('--fine')
        suffix=f'-fine{fine}' if fine else ''
        receipt=json.loads((ROOT/f'out/sophie-port/t{track}-{case}-metal{metal}{suffix}/receipt.json').read_text())
        assert receipt['image_sha256']==identities['out/mainos_bus.bin'], \
            'Sophie case used a different image'
    subprocess.run([sys.executable,'tools/verify/verify_sophie_page.py'],cwd=ROOT,check=True)
    unchanged()
    (frozen/'verified-inputs.json').write_text(json.dumps(identities,indent=2)+'\n')
if __name__=='__main__':main()
