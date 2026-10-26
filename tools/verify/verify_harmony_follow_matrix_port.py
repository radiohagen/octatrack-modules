#!/usr/bin/env python3
"""Full-sequencer source/follower, KEY, response and arp composition matrix."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import itertools
import json
import os
import shutil
from pathlib import Path
import verify_midi_harmony_port as port
import emu_card
from hw import ot_project as otp


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project',type=Path,required=True)
    ap.add_argument('--workers',type=int,default=3)
    ap.add_argument('--resume',action='store_true',help='reuse recorded cases only for the same image; retain the original project template')
    args=ap.parse_args()
    port.OUT=port.ROOT/'out/harmony-follow-matrix'
    image=port.freeze_candidate(port.OUT)
    has_scales='ms_snap' in port.harmony.symbols()
    keys=(0,1,25) if has_scales else (0,1,2)
    cases=list(itertools.product(range(3),range(3),keys,range(2),range(2)))
    digest=hashlib.sha256(image.read_bytes()).hexdigest()
    results={}
    receipt=port.OUT/'results.json'
    if args.resume and receipt.exists():
        previous=json.loads(receipt.read_text())
        assert previous['image_sha256']==digest, 'resume image changed'
        results=previous['cases']
    def name_for(case):
        sh,fh,key,response,arp=case
        return f's{sh}-f{fh}-k{key}-live{response}-arp{arp}'
    def cleanup(name):
        if os.environ.get('KEEP_CARDS')=='1': return
        work=port.OUT/name
        for filename in ('card.img','matrix-card.img'):
            (work/filename).unlink(missing_ok=True)
        for dirname in ('tree','project'):
            path=work/dirname
            if path.is_dir() and not path.is_symlink(): shutil.rmtree(path)
    for name in results: cleanup(name)
    def run(case):
        sh,fh,key,response,arp=case
        name=name_for(case)
        work=port.fixture(args.project,name,{0:sh,1:fh},arp=bool(arp),key_raw=key,first_note=60)
        for path in (work/'project').glob('bank*.work'):
            def mutate(data):
                for part in range(8):
                    base=otp.PART_BASE+part*otp.PART_STRIDE+9
                    data[base+0x4e2+36+3]=1
                    data[base+0x4e2+36+12]=response<<1
                    data[base+0x4e2+36+17]=key
                for pat in range(16):
                    for track in (0,1):
                        at=0x492e+pat*0x8eec+track*0x8b9
                        for step in range(64):
                            lock=at+0x39+step*32
                            data[lock+3:lock+6]=bytes((68,71,76) if track==0 else (255,255,255))
                        if track==0:
                            data[at+0x39+4*32]=62
                            data[at+0x39+8*32]=65
            otp._bank_write(work/'project',int(path.stem[4:]),mutate,guard=False)
        card,_=emu_card.stage_project(work/'project','OCTABAM','BASS',tree=work/'tree')
        (work/'card.img').write_bytes(card)
        events=port.run(work,'matrix',['--sequencer','--internal-clock','--frames','7000'])
        port.balanced(events)
        notes=[e[2] for e in events if e[:2]==('on',2)]
        # Independent diatonic reference for these three C-rooted keys.
        degrees=(0,2,4,5,7,9,11) if key==1 else (0,2,3,5,7,9,10) if key==25 else (0,2,3,5,7,8,10)
        def snap(n):
            if not key:return n
            # Native C minor uses the stock correction; these chord tones
            # only exercise downward chromatic corrections, as does major.
            return max(x for x in range(n+1) if x%12 in degrees)
        def chord(root):
            if fh==1 or (fh==0 and sh):return [root]
            if fh==0:return [snap(root+n) for n in (0,4,7,12)]
            if not key:return [root,root+4,root+7]
            scale=[n for n in range(root,root+24) if n%12 in degrees]
            return [scale[i] for i in (0,2,4)]
        want=([48] if fh!=2 else chord(48))
        for root in ([36,36,38,38,41,41] if response else [36,36,38,41,41]):
            want += chord(root)
        if not arp:
            assert notes==want,(name,notes,want)
        else:
            allowed=set(want)
            assert len(notes)>6,(name,notes)
            assert set(notes)<=allowed,(name,notes,sorted(allowed))
        return name,dict(notes=notes,balanced_releases=True,exact_nonarp=(not arp),arp_pitch_material=(bool(arp)))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(run,case):case for case in cases if name_for(case) not in results}
        for future in as_completed(futures):
            name,result=future.result();results[name]=result
            print('[ok]',name,flush=True)
            receipt.write_text(json.dumps(dict(image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),cases=results,total=len(cases),hardware_tested=False),indent=2)+'\n')
            cleanup(name)
    print(f'[ok] {len(results)} full-firmware combinations: nine HARM pairs x three keys x TRIG/LIVE x arp off/on',flush=True)


if __name__=='__main__':main()
