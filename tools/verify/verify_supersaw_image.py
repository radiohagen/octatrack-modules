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
    # Earlier image-stage gates may build their own reference remix. Restore
    # this carrier before reading its image and linked symbols.
    remix = registry.remix(os.environ.get('REMIX','supersaw'))
    subprocess.run(['make','bus',f'REMIX={remix.name}'],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'tools/verify/verify_supersaw_cf.py'],cwd=ROOT,check=True)
    project = os.environ.get('OT_PROJECT')
    if not project:
        print('[SKIP] Supersaw full firmware: set OT_PROJECT to a local fixture')
        return
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
    name = prefix+'-panel-eight'
    subprocess.run([sys.executable,'tools/verify/verify_supersaw_panel.py',
        '--project',project,'--name',name],cwd=ROOT,check=True)
    receipts.append(str(ROOT/'out/supersaw-port'/name/'audio-ui-receipt.json'))
    name = prefix+'-panel-morph'
    subprocess.run([sys.executable,'tools/verify/verify_supersaw_panel.py',
        '--project',project,'--name',name,'--control','MORF'],cwd=ROOT,check=True)
    receipts.append(str(ROOT/'out/supersaw-port'/name/'audio-ui-receipt.json'))
    for mode in ('midi','sequence','transition'):
        name = prefix+'-poly-'+mode
        subprocess.run([sys.executable,'tools/verify/verify_supersaw_poly.py',
            '--project',project,'--name',name,'--mode',mode,
            *(['--rich'] if mode=='midi' else []),
            *(['--fx'] if mode=='midi' and pair=='SPECTRUM,CHARACTER' else [])],cwd=ROOT,check=True)
        receipts.append(str(ROOT/'out/supersaw-port'/name/'receipt.json'))
    (ROOT/'out/supersaw-qualification.json').write_text(json.dumps(dict(
        remix=remix.name,receipts=receipts,simultaneous_tracks=8,voices_per_track=4,polyphony_test_tracks=1,
        hardware_tested=False),indent=2)+'\n')

if __name__ == '__main__': main()
