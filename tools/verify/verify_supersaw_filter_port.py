#!/usr/bin/env python3
"""Actual SRC/SETUP encoders, four MIDI voices and preserved FLEX/FX settings."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,struct,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/verify')]
import toolpath,emu_card,blockdump,recloop,lcd_view,slots
from hw import ot_project as otp
from verify_supersaw_port import fixture,rms

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--project',type=Path,required=True);ap.add_argument('--name',required=True);a=ap.parse_args()
    w=ROOT/'out/supersaw-port'/a.name;w.mkdir(exist_ok=False)
    fixture(a.project,w,(0,),True,voices=4)
    for path in (w/'project').glob('bank*.work'):
        def edit(d):
            for part in range(8):
                b=otp.PART_BASE+part*otp.PART_STRIDE+9
                d[b+0x11a+6:b+0x11a+12]=bytes((32,127,78,64,64,127))
        otp._bank_write(w/'project',int(path.stem[4:]),edit,guard=False)
    card,_=emu_card.stage_project(w/'project','OCTABAM','SYNTH',tree=w/'tree2',audio=[f'{w}/FMSYNTH-SUPERSAW.wav:AUDIO/FMSYNTH-SUPERSAW.wav']);(w/'card.img').write_bytes(card)
    shutil.copy2(ROOT/'out/mainos_bus.bin',w/'candidate.bin')
    raw=subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True);sym={f[2]:int(f[0],16) for line in raw.splitlines() if len(f:=line.split())==3}
    rows=[]
    def key(ms,k):rows.extend((f'{ms} key {k:#x} down',f'{ms+40} key {k:#x} up'))
    key(0,0x32);rows.append('100 pot 128');key(200,0x10)
    rows+=['400 key 0x2d down','440 key 0x22 down','480 key 0x22 up','520 key 0x2d up']
    for ms,knob,delta in ((800,0,12),(900,1,24),(1000,2,64),(1100,3,24),(1200,4,1)):
        rows.append(f'{ms} enc {knob} {delta}')
    rows.append(f'1500 wait {sym["ss_setup"]:#x} 4c4040580153 eq 1')
    key(1700,0x32);key(1900,0x22);rows.append('2100 enc 3 -70');rows.append('2300 wait 0x80000813 39 eq 1')
    for ms,note in ((2500,84),(2650,88),(2800,91),(2950,95)):rows.append(f'{ms} midi 90 {note:02x} 64')
    rows.append('4100 midi 80 54 00')
    for i,note in enumerate((88,91,95)):rows.append(f'{4800+10*i} midi 80 {note:02x} 00')
    rows+=['5800 key 0x2d down','5840 key 0x22 down','5880 key 0x22 up','5920 key 0x2d up','6200 quit']
    rows.sort(key=lambda r:int(r.split()[0]));(w/'panel.script').write_text('\n'.join(rows)+'\n')
    dumps=';'.join(f'{sym[k]:#x},{size}={w}/{k}.bin' for k,size in [('ss_setup',48),('ss_filters',8*5*36),('ss_filter_samples',32),('ss_native_voices',2048),('ss_descriptor',402)])
    dumps+=f';0x100a4ece,6322={w}/shadow.bin;0x80000810,576={w}/lanes.bin;0x80000110,512={w}/dsp-records.bin'
    cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(w/'candidate.bin'),'--card',str(w/'card.img'),'--set','OCTABAM','--project','SYNTH','--mkii','--load-ms','90000','--dsp','--internal-clock','--live-script',str(w/'panel.script'),'--audio-out',str(w/'audio'),'--block-dump',str(w/'blocks.bin'),'--lcd',str(w/'lcd.bin'),'--mem-dump',dumps]
    (w/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
    with slots.slot('Supersaw SEM panel/audio',root=ROOT) as env:
        with (w/'port.log').open('w') as log:r=subprocess.run(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
    assert r.returncode==0
    log=(w/'port.log').read_text();assert 'ended on quit' in log and 'LOAD PROJECT handled' in log
    assert 'WAIT TIMEOUT' not in log and 'DID NOT RETURN' not in log and 'unimplemented opcode' not in log
    setup=(w/'ss_setup.bin').read_bytes();assert setup[:6]==bytes((76,64,64,88,1,83)),setup[:6]
    shadow=(w/'shadow.bin').read_bytes();assert shadow[0x1ec:0x1f2]==setup[:6]
    original=(w/'project/bank01.work').read_bytes();base=otp.PART_BASE+9
    assert shadow[0x1e0:0x1e6]==original[base+0x1e0:base+0x1e6],'FLEX setup changed'
    desc=(w/'ss_descriptor.bin').read_bytes()
    for i,name in enumerate(('PTCH','DETU','MORF','CUT','SUB','DRIV','FINE','RES','ENV','DEC','TYPE','')):
        assert desc[0x16+6*i:0x1c+6*i]==name.encode().ljust(6,b'\0')
    pool=(w/'ss_native_voices.bin').read_bytes();assert all(pool[v*64+36]==0 for v in range(4))
    counts=struct.unpack('>8I',(w/'ss_filter_samples.bin').read_bytes());assert counts[0]>250000 and not any(counts[1:])
    n=int(re.search(r'over (\d+) frames, ended on quit',log)[1]);rows=blockdump.read(w/'blocks.bin');end=max(r[1] for r in rows);rows=[r for r in rows if r[1]>end-n]
    for core in (0,1):assert [r[1] for r in rows if r[0]=='<' and r[2]==1 and r[3]==core]==list(range(1,n))
    source=recloop.track_audio(blockdump.classes(rows),1);assert rms(source[int(3.2*44100):int(4*44100)])>100;assert rms(source[int(6*44100):int(6.15*44100)])<8
    records=(w/'dsp-records.bin').read_bytes()
    for off,field in ((otp.FX1_OFF,54),(otp.FX2_OFF,56)):
        assert [int.from_bytes(records[t*64+field:t*64+field+2],'big') for t in range(8)]==list(original[otp.PART_BASE+off:otp.PART_BASE+off+8])
    data=lcd_view.read_plane(w/'lcd.bin');lcd_view.png(lcd_view.composite(lcd_view.pixels(data),data),w/'lcd.png')
    receipt=dict(result='pass',image_sha256=hashlib.sha256((w/'candidate.bin').read_bytes()).hexdigest(),real_encoders=True,setup=list(setup[:6]),filter_samples=counts,source_tail_silent=True,fx_assignments_unchanged=True,flex_setup_unchanged=True,frames=n-1,hardware_tested=False)
    (w/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('[ok] SEM setup/main encoders, four notes, releases, DSP continuity and unchanged FLEX/FX settings')
if __name__=='__main__':main()
