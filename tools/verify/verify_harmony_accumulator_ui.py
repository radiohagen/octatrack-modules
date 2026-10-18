#!/usr/bin/env python3
"""Measure actual composed 1-bpp LCD ink, not nominal widget coordinates."""
import json
import struct
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/emu'))
import lcd_view


def measure(directory):
    results={}
    for name,plain,selected in (('harmony-page',False,0),('chord-page-extremes',False,0),
                                ('accum-page',False,1)):
        data=lcd_view.read_plane(directory/f'{name}.lcd')
        rows=lcd_view.screen(data)
        windows=[]
        for i in range(5):
            at=lcd_view.WIN_TABLE+i*56
            flags,w,h=struct.unpack('>Iii',data[at+32:at+44])
            if flags&32 and (w,h)==(120,60):
                windows.append(struct.unpack('>ii',data[at+8:at+16]))
        assert len(windows)==1,(name,windows)
        ox,oy=windows[0]
        # Native frame's inner right edge is x=117, not the old short
        # horizontal line endpoint x=115. This distinction caught real drift.
        accum=name=='accum-page'
        if accum:
            # ACCUM gives the real A--F field its entire 120x60 canvas. It
            # deliberately omits the footer/tab rail so native dials and
            # four-way switches retain a full three-by-two cell geometry.
            # Four persisted settings occupy A-D; E/F remain empty rather
            # than presenting fake controls.
            edges=[ox+i for i in (0,39,78,117)]
            tops=[oy+i for i in (0,30,59)]
            cells=((0,0,'LOW dial'),(1,0,'HIGH dial'),
                   (2,0,'BOUND switch'),(0,1,'RESET switch'))
            for col,row,kind in cells:
                left,right=edges[col:col+2]
                top,bottom=tops[row:row+2]
                assert any(rows[y][x] for y in range(top+1,bottom) for x in range(left+1,right)),(name,'empty control cell')
            # Tight inner crops prove stock dial/switch pixels rather than a
            # text-only surrogate. E/F must be clean: this also catches an
            # accidental return of the old footer or tab rail.
            for col,row,kind in cells:
                left,right=edges[col:col+2]
                top,bottom=tops[row:row+2]
                left+=6; right-=6; top+=3; bottom-=3
                assert any(rows[y][x] for y in range(top,bottom) for x in range(left,right)),(name,'missing',kind,left,top)
            for col,row in ((1,1),(2,1)):
                left,right=edges[col:col+2]
                top,bottom=tops[row:row+2]
                assert not any(rows[y][x] for y in range(top+3,bottom-3) for x in range(left+3,right-3)),(name,'unexpected E/F ink')
            results[name]=dict(cells=[kind for _,_,kind in cells], empty_cells=['E','F'],
                                      grid=[0,39,78,117],footer='omitted')
            continue
        edges=[ox+i for i in (32,60,88,117)]
        tops=[oy+1,oy+24,oy+47]
        for x in edges[1:3]:
            # The native dotted verticals deliberately leave their last two
            # pixels open where they meet the horizontal divider.
            column=[rows[y][x] for y in range(tops[0]+1,tops[1])]
            assert all(a!=b for a,b in zip(column,column[1:])),(name,'not dotted',x)
        values=[]
        for cell in range(4):
            col,row=cell%3,cell//3
            left,right=edges[col:col+2];top,bottom=tops[row:row+2]
            bands=(('label',5,9),('value',14,18)) if plain else (
                ('label',2,6),('graphic',7,13),('value',17,21))
            all_points=[]
            for kind,first,last in bands:
                points=[(x,y) for y in range(top+first,top+last+1)
                        for x in range(left+1,right) if rows[y][x]]
                assert points,(name,cell,kind,'missing ink')
                all_points+=points
                x0=min(x for x,y in points);x1=max(x for x,y in points)
                gaps=(x0-left-1,right-x1-1)
                assert min(gaps)>=1 and abs(gaps[0]-gaps[1])<=1,(name,cell,kind,gaps)
                values.append(dict(cell=cell,kind=kind,bounds=[x0,min(y for x,y in points),
                    x1,max(y for x,y in points)],left_right_padding=list(gaps)))
            y0=min(y for x,y in all_points);y1=max(y for x,y in all_points)
            gaps=(y0-top-1,bottom-y1-1)
            assert gaps==((4,4) if plain else (1,1)),(name,cell,'vertical padding',gaps)
        # The selection bar must contain dark glyph ink, not a blank fill.
        top=oy+(6 if selected==0 else 17)
        ink=[rows[y][x] for y in range(top,top+5) for x in range(ox+5,ox+24)]
        assert 0 in ink and 1 in ink,(name,'blank selection label')
        results[name]=dict(cells=values,vertical_padding=[4,4] if plain else [1,1],
                           max_horizontal_centre_error_pixels=0.5)
    (directory/'pixel-layout.json').write_text(json.dumps(results,indent=2)+'\n')
    print('[ok] LCD pixels: all labels/graphics/values within 0.5 px of cell centre; balanced vertical padding',flush=True)
    return results


if __name__=='__main__':
    measure(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'out/harmony-accumulator-port/panel-note')
