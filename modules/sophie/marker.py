#!/usr/bin/env python3
"""Write a silent marker for Sophie; its filename activates the firmware engine."""
import argparse
from pathlib import Path
import wave

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    if args.output.name != 'FMSYNTH-SOPHIE.wav':
        parser.error('output filename must be FMSYNTH-SOPHIE.wav')
    if args.output.exists():
        parser.error('output already exists; choose a new directory')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(args.output),'wb') as out:
        out.setparams((1,2,44100,0,'NONE','not compressed'))
        out.writeframes(bytes(4*44100*2))
    print(args.output.resolve())
if __name__=='__main__':main()
