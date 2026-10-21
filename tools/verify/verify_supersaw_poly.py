#!/usr/bin/env python3
"""Full-firmware four-note MIDI chords, stealing, selective release and retrigger."""
import argparse,hashlib,json,math,re,shutil,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import toolpath,blockdump,recloop
from hw import ot_project as otp
from verify_supersaw_port import fixture,rms
import numpy as np


def spectrum(audio,start,end,notes):
    x=np.asarray(audio[int(start*44100):int(end*44100)],dtype=float)
    power=np.abs(np.fft.rfft(x*np.hanning(len(x))))
    freqs=np.fft.rfftfreq(len(x),1/44100)
    # Synth MIDI 84 is C4 in the pinned native engine.
    return {str(note):float(max(power[np.abs(freqs-440*2**((note-93)/12))<10])) for note in notes}


def analyze(work,tracks,voices,rich,mode="midi"):
    log=(work/'port.log').read_text()
    assert 'ended on quit' in log and 'LOAD PROJECT handled' in log
    assert all(x not in log for x in ('WAIT TIMEOUT','ended early','unimplemented opcode','DID NOT RETURN'))
    n=int(re.search(r'over (\d+) frames, ended on quit',log)[1])
    rows=blockdump.read(work/'blocks.bin');end=max(r[1] for r in rows)
    rows=[r for r in rows if r[1]>end-n]
    for core in (0,1):
        frames=[r[1] for r in rows if r[0]=='<' and r[2]==1 and r[3]==core]
        assert frames==list(range(1,n)),('DSP continuity',core,len(frames),n)
    classes=blockdump.classes(rows);notes=[84,88,91,95][:voices];all_notes=notes+[98]
    metrics={}
    for t in tracks:
        source=recloop.track_audio(classes,t+1);out=recloop.readback_audio(classes,t+1)
        assert len(source)==len(out)==(n-1)*16
        if mode=='sequence':
            chord=spectrum(source,.75,.9,notes)
            assert all(x>max(chord.values())*.06 for x in chord.values()),('sequencer chord',t,chord)
            assert rms(source[int(.75*44100):int(.9*44100)])>100
            assert rms(source[int(1.35*44100):int(1.55*44100)])<8,('HOLD release',t)
            metrics[f'T{t+1}']=dict(sequencer_chord=chord)
            continue
        if mode=='transition':
            mono=spectrum(source,1.,1.2,[80])
            chord=spectrum(source,2.1,2.3,notes)
            back=spectrum(source,3.1,3.3,all_notes)
            assert mono['80']>1000
            assert all(x>max(chord.values())*.06 for x in chord.values()),('mono to poly',t,chord)
            assert back['98']>1000 and all(back[str(note)]<back['98']*.1 for note in notes),('poly to mono',t,back)
            assert rms(source[int(4.1*44100):int(4.3*44100)])<8
            metrics[f'T{t+1}']=dict(mono=mono,chord=chord,back_to_mono=back)
            continue
        before=spectrum(source,1.35,1.65,all_notes)
        stolen=spectrum(source,2.35,2.65,all_notes)
        released=spectrum(source,3.15,3.45,all_notes)
        again=spectrum(source,4.65,4.85,all_notes)
        for note in notes: assert before[str(note)]>max(before.values())*.06,('missing chord note',t,note,before)
        assert stolen['84']<before['84']*.15,('oldest note not stolen',t,before,stolen)
        assert stolen['98']>max(stolen.values())*.06,('fifth note missing',t,stolen)
        assert released['88']<stolen['88']*.15,('selective note-off',t,stolen,released)
        for note in notes[2:]+[98]: assert released[str(note)]>max(released.values())*.06,('other note released',t,note,released)
        for note in notes: assert again[str(note)]>max(again.values())*.06,('retrigger',t,note,again)
        assert rms(source[int(4.1*44100):int(4.3*44100)])<8
        assert rms(source[int(5.3*44100):int(5.45*44100)])<8
        assert rms(out[44100:int(1.8*44100)])>100
        metrics[f'T{t+1}']=dict(chord=before,stolen=stolen,selective_release=released,retrigger=again)
    counts=struct.unpack('>32I',(work/'ss_poly_samples.bin').read_bytes())
    for t in range(8):
        used=sum(x>0 for x in counts[t*4:t*4+4])
        assert used>=voices if t in tracks else used==0,(t,used,counts)
    assert (work/'ss_unsupported.bin').read_bytes()==bytes(32)
    records=(work/'dsp-records.bin').read_bytes();bank=(work/'project/bank01.work').read_bytes()
    for off,field in ((otp.FX1_OFF,54),(otp.FX2_OFF,56)):
        assert [int.from_bytes(records[t*64+field:t*64+field+2],'big') for t in range(8)]==list(bank[otp.PART_BASE+off:otp.PART_BASE+off+8])
    result=dict(result='pass',image_sha256=hashlib.sha256((work/'candidate.bin').read_bytes()).hexdigest(),voices_per_track=voices,tracks=[t+1 for t in tracks],rich=rich,mode=mode,frames=n-1,audio=metrics,poly_samples=counts,hardware_tested=False)
    (work/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'[ok] {voices}-note Supersaw {mode} on {len(tracks)} tracks: audio/lifecycle assertions, DSP continuity and unchanged FX slots',flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,required=True);p.add_argument('--name',required=True)
    p.add_argument('--mode',choices=('midi','sequence','transition'),default='midi');p.add_argument('--tracks',default='1');p.add_argument('--voices',type=int,choices=(2,3,4),default=4);p.add_argument('--rich',action='store_true')
    a=p.parse_args();tracks=tuple(int(t)-1 for t in a.tracks.split(','));assert len(set(tracks))==len(tracks) and all(0<=t<8 for t in tracks)
    work=ROOT/'out/supersaw-port'/a.name;work.mkdir(parents=True,exist_ok=False)
    assert a.mode=='midi' or (a.voices==4 and tracks==(0,))
    fixture(a.project,work,tracks,a.rich,sequence=a.mode=='sequence',
            voices=1 if a.mode=='transition' else a.voices,chord=28 if a.mode=='sequence' else 0,
            hold=32 if a.mode=='sequence' else 127)
    shutil.copy2(ROOT/'out/mainos_bus.bin',work/'candidate.bin')
    raw=subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True)
    sym={f[2]:int(f[0],16) for line in raw.splitlines() if len(f:=line.split())==3}
    notes=[84,88,91,95][:a.voices]
    rows=['0 key 0x32 down','40 key 0x32 up','100 pot 128','200 key 0x10 down','240 key 0x10 up','400 key 0x22 down','440 key 0x22 up','660 key 0x28 down','700 key 0x28 up']
    events=[(800,True,notes),(2000,True,[98]),(2800,False,[88]),(3700,False,notes+[98]),(4500,True,notes),(5000,False,notes)]
    if a.mode=='sequence': events=[]
    if a.mode=='transition':
        events=[(800,True,[80]),(1800,True,notes),(2800,True,[98]),(3700,False,notes+[80,98])]
        lane=0x80000818
        rows+=['1200 key 0x24 down','1240 key 0x24 up','1400 enc 2 3',f'1600 wait {lane:#x} 04 eq 1',
               '2400 enc 2 -3',f'2600 wait {lane:#x} 01 eq 1']
    for ms,on,keys in events:
        for t in tracks:
            for key in keys:rows.append(f'{ms} midi {(0x90 if on else 0x80)+t:02x} {key:02x} {"64" if on else "00"}')
    rows+=['5500 quit'];rows.sort(key=lambda row:int(row.split()[0]));(work/'panel.script').write_text('\n'.join(rows)+'\n')
    dumps=f'{sym["ss_poly_samples"]:#x},128={work}/ss_poly_samples.bin;{sym["ss_unsupported"]:#x},32={work}/ss_unsupported.bin;0x80000110,512={work}/dsp-records.bin;{sym["ss_native_voices"]:#x},2048={work}/native-voices.bin'
    cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(work/'candidate.bin'),'--card',str(work/'card.img'),'--set','OCTABAM','--project','SYNTH','--mkii','--load-ms','90000','--dsp','--internal-clock','--live-script',str(work/'panel.script'),'--audio-out',str(work/'audio'),'--block-dump',str(work/'blocks.bin'),'--mem-dump',dumps]
    (work/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
    with (work/'port.log').open('w') as log:r=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=300)
    assert r.returncode==0,work/'port.log'
    analyze(work,tracks,a.voices,a.rich,a.mode)

if __name__=='__main__':main()
