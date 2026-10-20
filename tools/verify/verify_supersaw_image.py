#!/usr/bin/env python3
"""Exact-image Supersaw qualification using disposable project copies."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import toolpath
from remix import registry


def main():
    subprocess.run([sys.executable,'tools/verify/verify_supersaw_cf.py'],cwd=ROOT,check=True)
    project = os.environ.get('OT_PROJECT')
    if not project:
        print('[SKIP] Supersaw full firmware: set OT_PROJECT to a local fixture')
        return
    remix = registry.remix(os.environ.get('REMIX','supersaw'))
    modules = set(remix.modules)
    pair = 'SPECTRUM,CHARACTER' if {'SPECTRUM','CHARACTER'} <= modules else 'FILTER,DELAY'
    assert set(pair.split(',')) <= modules, 'qualify a fixture using the selected effects'
    prefix = f'gate-{time.time_ns()}'
    receipts = []
    for case,args in [('dual',['--rich']),('sequence',['--sequence']),
                      ('mixed-fx',['--mixed','--fx','--fx-pair',pair])]:
        name = prefix+'-'+case
        subprocess.run([sys.executable,'tools/verify/verify_supersaw_port.py',
            '--project',project,'--name',name,*args],cwd=ROOT,check=True)
        path = ROOT/'out/supersaw-port'/name
        receipts.append(str(path/'receipt.json'))
    subprocess.run([sys.executable,'tools/verify/verify_supersaw_page.py',
        '--fixture',str(path)],cwd=ROOT,check=True)
    (ROOT/'out/supersaw-qualification.json').write_text(json.dumps(dict(
        remix=remix.name,receipts=receipts,simultaneous_tracks=2,
        hardware_tested=False),indent=2)+'\n')

if __name__ == '__main__': main()
