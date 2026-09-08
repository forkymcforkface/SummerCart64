"""Generate disposable RTL differential vectors from original GIF bytes."""
from pathlib import Path
import argparse, hashlib, json, struct
from gif_reference import read_gif, decode
args=argparse.ArgumentParser()
args.add_argument('original',type=Path)
args.add_argument('output',type=Path)
args=args.parse_args()
root=args.output;root.mkdir(parents=True,exist_ok=True)
w,h,bg,palette,frames=read_gif(args.original)
records=[]
for f in frames:
    expected,_=decode(f['raw'],f['bits'],f['w']*f['h'])
    records.append((f['bits'],len(expected),f['raw'],expected,0))
(root/'manifest.json').write_text(json.dumps(dict(source=str(args.original),sha256=hashlib.sha256(args.original.read_bytes()).hexdigest(),original_frames=len(frames),width=w,height=h,background=bg,global_palette=list(palette),frames=[{k:v for k,v in f.items() if k not in ('raw','pal')} for f in frames]),indent=2))
def pack(codes,minimum):
    clear=1<<minimum;end=clear+1;size=minimum+1;nxt=end+1;prev=False;acc=nb=0;out=bytearray()
    for code in codes:
        acc|=code<<nb;nb+=size
        while nb>=8:out.append(acc&255);acc>>=8;nb-=8
        if code==clear:size=minimum+1;nxt=end+1;prev=False
        elif code!=end:
            if prev and nxt<4096:
                nxt+=1
                if nxt==1<<size and size<12:size+=1
            prev=True
    if nb:out.append(acc&255)
    return out
for minimum in range(2,9):
    clear=1<<minimum;end=clear+1
    for length in (1,17,4096,10000):
        codes=[clear]+[i%clear for i in range(length)]+[end]
        expected=bytes(i%clear for i in range(length))
        records.append((minimum,length,pack(codes,minimum),expected,0))
    records.append((minimum,1,pack([clear,end+2,end],minimum),b'',1))
    records.append((minimum,0,pack([clear,0,end],minimum),b'',1))
    records.append((minimum,2,pack([clear,0,end],minimum),b'\0',1))
for minimum in (0,1,9,15):records.append((minimum,0,b'',b'',1))
records.append((8,1,pack([256,0,257],8)[:-1],b'\0',1))
records.append((8,1,b'',b'',1))
with (root/'fixtures.bin').open('wb') as out:
    out.write(struct.pack('<II',len(records),len(frames)))
    for minimum,limit,raw,expected,error in records:
        out.write(struct.pack('<IIIII',minimum,limit,len(raw),len(expected),error));out.write(raw);out.write(expected)
print('RTL fixtures',len(records))
