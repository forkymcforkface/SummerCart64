"""Independent bounded GIF framing/LZW reference for experimental RTL tests."""
import struct

def read_gif(path):
    data = path.read_bytes()
    pos = 6
    w,h,packed,bg,aspect = struct.unpack_from('<HHBBB', data,pos); pos+=7
    gct = data[pos:pos+3*(2**((packed&7)+1))] if packed&128 else b''
    pos += len(gct)
    frames=[]; gce=(0,0,False,0)
    def blocks():
        nonlocal pos
        out=bytearray()
        while True:
            n=data[pos];pos+=1
            if not n:return bytes(out)
            assert pos+n <= len(data)
            out.extend(data[pos:pos+n]);pos+=n
    while pos < len(data):
        tag=data[pos];pos+=1
        if tag==59:break
        if tag==33:
            label=data[pos];pos+=1
            b=blocks()
            if label==249:
                assert len(b)==4
                gce=((b[0]>>2)&7,int.from_bytes(b[1:3],'little')*10,bool(b[0]&1),b[3])
        elif tag==44:
            x,y,fw,fh,p=struct.unpack_from('<HHHHB',data,pos);pos+=9
            pal=data[pos:pos+3*(2**((p&7)+1))] if p&128 else gct
            if p&128:pos+=len(pal)
            bits=data[pos];pos+=1
            raw=blocks()
            assert x+fw<=w and y+fh<=h
            frames.append(dict(x=x,y=y,w=fw,h=fh,interlace=bool(p&64),local=bool(p&128),pal=pal,bits=bits,raw=raw,gce=gce))
            gce=(0,0,False,0)
        else:raise ValueError((pos,tag))

    return w,h,bg,gct,frames

def decode(raw,minimum,limit):
    clear=1<<minimum; end=clear+1
    table={i:bytes([i]) for i in range(clear)}
    size=minimum+1; nxt=end+1; prev=None; acc=0; nbits=0; out=bytearray()
    codes=clears=kw=walk=0; longest=0; peak=nxt
    for b in raw:
        acc |= b<<nbits;nbits+=8
        while nbits>=size:
            code=acc&((1<<size)-1);acc>>=size;nbits-=size;codes+=1
            if code==clear:
                table={i:bytes([i]) for i in range(clear)};size=minimum+1;nxt=end+1;prev=None;clears+=1
                continue
            if code==end:
                assert len(out)==limit
                return out,dict(codes=codes,clears=clears,kwkwk=kw,prefix_walk_entries=walk,max_phrase=longest,peak_dictionary=peak)
            if code in table:phrase=table[code]
            else:
                assert code==nxt and prev is not None
                phrase=prev+prev[:1];kw+=1
            out.extend(phrase);walk+=max(0,len(phrase)-1);longest=max(longest,len(phrase))
            assert len(out)<=limit
            if prev is not None and nxt<4096:
                table[nxt]=prev+phrase[:1];nxt+=1;peak=max(peak,nxt)
                if nxt==(1<<size) and size<12:size+=1
            prev=phrase
    raise ValueError('missing LZW end')
