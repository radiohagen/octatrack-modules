#!/usr/bin/env python3
"""Native SETUP edits, SAVE PROJECT and cold reload on a disposable card."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/verify')]
import toolpath,emu_card,slots
from hw import ot_project as otp
from verify_supersaw_port import fixture

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--project',type=Path,required=True);ap.add_argument('--name',required=True);a=ap.parse_args()
    w=ROOT/'out/supersaw-port'/a.name;w.mkdir(exist_ok=False)
    fixture(a.project,w,(0,),True,voices=4)
    shutil.copy2(ROOT/'out/mainos_bus.bin',w/'candidate.bin')
    raw=subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True)
    sym={f[2]:int(f[0],16) for line in raw.splitlines() if len(f:=line.split())==3}
    expected=bytes((76,64,64,88,1,83));rows=[]
    def key(ms,k):rows.extend((f'{ms} key {k:#x} down',f'{ms+80} key {k:#x} up'))
    key(0,0x32);key(200,0x10)
    rows+=['400 key 0x2d down','440 key 0x22 down','480 key 0x22 up','520 key 0x2d up']
    for ms,knob,delta in ((800,0,12),(900,1,24),(1000,2,64),(1100,3,24),(1200,4,1)):rows.append(f'{ms} enc {knob} {delta}')
    rows.append(f'1400 wait {sym["ss_setup"]:#x} {expected.hex()} eq 1')
    key(1600,0x32);key(1800,0x22);rows.append('2000 enc 3 -70')
    for ms,k in ((2500,0x1c),(3500,0x21),(4200,0x20),(4900,0x31),(5600,0x31)):key(ms,k)
    rows.append('40000 quit');rows.sort(key=lambda r:int(r.split()[0]));(w/'save.txt').write_text('\n'.join(rows)+'\n')
    reload=['0 key 0x32 down','80 key 0x32 up','200 key 0x10 down','280 key 0x10 up','400 key 0x22 down','480 key 0x22 up',f'1000 wait {sym["ss_setup"]:#x} {expected.hex()} eq 1','1500 quit']
    (w/'reload.txt').write_text('\n'.join(reload)+'\n')
    with slots.slot('Supersaw native save/reload',root=ROOT) as env:
        for stage,card in (('save','card.img'),('reload','saved.img')):
            cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(w/'candidate.bin'),'--card',str(w/card),'--set','OCTABAM','--project','SYNTH','--mkii','--load-ms','90000','--live-script',str(w/(stage+'.txt')),'--mem-dump',f'0x100a4ece,6322={w}/{stage}-shadow.bin']
            if stage=='save':cmd+=['--card-out',str(w/'saved.img')]
            (w/(stage+'-command.json')).write_text(json.dumps(cmd,indent=2)+'\n')
            with (w/(stage+'.log')).open('w') as log:r=subprocess.run(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
            assert r.returncode==0
            log=(w/(stage+'.log')).read_text();assert 'ended on quit' in log and 'LOAD PROJECT handled' in log
            assert all(x not in log for x in ('WAIT TIMEOUT','DID NOT RETURN','unimplemented opcode'))
            shadow=(w/(stage+'-shadow.bin')).read_bytes();assert shadow[0x1ec:0x1f2]==expected,(stage,shadow[0x1ec:0x1f2])
            assert shadow[0x33]==57,(stage,'CUT',shadow[0x33])
    before=emu_card.extract_image((w/'card.img').read_bytes());after=emu_card.extract_image((w/'saved.img').read_bytes())
    b=otp.PART_BASE+9
    for suffix in ('work','strd'):
        data=after[f'OCTABAM/SYNTH/bank01.{suffix}'];assert data[b+0x1ec:b+0x1f2]==expected
        assert data[b+0x33]==57
        assert data[b+0x1e0:b+0x1e6]==before['OCTABAM/SYNTH/bank01.work'][b+0x1e0:b+0x1e6]
    receipt=dict(result='pass',image_sha256=hashlib.sha256((w/'candidate.bin').read_bytes()).hexdigest(),setup=list(expected),cut=57,native_save_project=True,cold_reload=True,work_and_strd=True,flex_setup_unchanged=True,hardware_tested=False)
    (w/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('[ok] SETUP/CUT edits survive native SAVE PROJECT and cold disk reload')
if __name__=='__main__':main()
