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


def parse_case(text):
    try:
        case=tuple(int(value) for value in text.split(','))
    except ValueError as error:
        raise argparse.ArgumentTypeError('case must contain five comma-separated integers') from error
    if len(case)!=5:
        raise argparse.ArgumentTypeError('case must be sourceMode,followerMode,key,response,arp')
    sh,fh,key,response,arp=case
    if sh not in range(3) or fh not in range(3):
        raise argparse.ArgumentTypeError('sourceMode and followerMode must be 0 (OFF), 1 (NOTE) or 2 (CHORD)')
    if not 0<=key<=127 or response not in range(2) or arp not in range(2):
        raise argparse.ArgumentTypeError('key must be 0..127; response and arp must be 0 or 1')
    return case


def compare_events(name,result,baseline):
    assert name in baseline['cases'], (name,'missing baseline case')
    expected=baseline['cases'][name].get('events')
    assert expected is not None, (name,'baseline has no complete event sequence; record it with this verifier')
    actual=result.get('events')
    assert actual is not None, (name,'result has no complete event sequence; rerun without --resume')
    for index,(got,want) in enumerate(itertools.zip_longest(actual,expected)):
        assert got==want, (name,'event sequence differs',index,got,want)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project',type=Path,required=True)
    ap.add_argument('--workers',type=int,default=3)
    ap.add_argument('--case',type=parse_case,action='append',help='select sourceMode,followerMode,key,response,arp; repeat for multiple cases (default: full matrix)')
    ap.add_argument('--output',type=Path,help='artifact directory for frozen image, symbols, case logs and results.json')
    ap.add_argument('--compare',type=Path,help='baseline results.json whose complete MIDI event sequences must match')
    ap.add_argument('--resume',action='store_true',help='reuse recorded cases only for the same image; retain the original project template')
    args=ap.parse_args()
    if args.workers<1: ap.error('--workers must be positive')
    port.OUT=(args.output or port.ROOT/'out/harmony-follow-matrix').resolve()
    receipt=port.OUT/'results.json'
    baseline=json.loads(args.compare.read_text()) if args.compare else None
    if args.compare and args.compare.resolve()==receipt.resolve():
        ap.error('--compare must be a separate receipt; choose another --output directory')
    image=port.freeze_candidate(port.OUT)
    has_scales='ms_snap' in port.harmony.symbols()
    keys=(0,1,25) if has_scales else (0,1,2)
    cases=list(dict.fromkeys(args.case)) if args.case else list(itertools.product(range(3),range(3),keys,range(2),range(2)))
    for case in cases:
        if case[2] not in keys:
            ap.error(f'key {case[2]} is not available in this matrix/image; choose from {keys}')
    digest=hashlib.sha256(image.read_bytes()).hexdigest()
    results={}
    if args.resume and receipt.exists():
        previous=json.loads(receipt.read_text())
        assert previous['image_sha256']==digest, 'resume image changed'
        results=previous['cases']
    def name_for(case):
        sh,fh,key,response,arp=case
        return f's{sh}-f{fh}-k{key}-live{response}-arp{arp}'
    for case in cases:
        name=name_for(case)
        if name in results:
            assert 'events' in results[name], (name,'resume lacks complete events; rerun without --resume')
    if baseline is not None:
        for case in cases:
            name=name_for(case)
            assert name in baseline['cases'], (name,'missing baseline case')
            assert 'events' in baseline['cases'][name], (name,'baseline lacks complete events; record it with this verifier')
            if name in results: compare_events(name,results[name],baseline)
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
        result=dict(notes=notes,events=[list(event) for event in events],balanced_releases=True,exact_nonarp=(not arp),arp_pitch_material=(bool(arp)))
        if baseline is not None:
            compare_events(name,result,baseline)
            result['exact_baseline_events']=True
        return name,result
    def write_receipt():
        receipt.write_text(json.dumps(dict(image_sha256=digest,comparison_image_sha256=baseline['image_sha256'] if baseline is not None else None,cases=results,total=len(cases),selected_cases=[name_for(case) for case in cases],hardware_tested=False),indent=2)+'\n')
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(run,case):case for case in cases if name_for(case) not in results}
        for future in as_completed(futures):
            name,result=future.result();results[name]=result
            print('[ok]',name,flush=True)
            write_receipt()
            cleanup(name)
    write_receipt()
    scope='selected' if args.case else 'full-matrix'
    comparison='; exact MIDI event sequences match baseline' if baseline is not None else ''
    print(f'[ok] {len(cases)} {scope} full-firmware combinations{comparison}',flush=True)


if __name__=='__main__':main()
