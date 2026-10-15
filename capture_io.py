"""Streaming PCAP/PCAPNG validation and exact-record deduplication."""
import hashlib
from pathlib import Path
import struct
from fractions import Fraction

MAX_BLOCK = 256 * 1024 * 1024

def exact_read(f, n):
    b=f.read(n)
    if len(b)!=n: raise ValueError('Truncated capture')
    return b

def clean_capture(source, target, remove=True):
    """Preserve originals; dedup within section/interface/time/bytes, per file."""
    total=kept=duplicates=untimed=0; first=last=None; seen=set(); digest=hashlib.sha256()
    with open(source,'rb') as f, open(target,'xb') as out:
        magic=exact_read(f,4); f.seek(0)
        if magic in (b'\xd4\xc3\xb2\xa1',b'\xa1\xb2\xc3\xd4',b'\x4d\x3c\xb2\xa1',b'\xa1\xb2\x3c\x4d'):
            header=exact_read(f,24); digest.update(header); out.write(header)
            end='<' if magic in (b'\xd4\xc3\xb2\xa1',b'\x4d\x3c\xb2\xa1') else '>'
            scale=10**9 if magic in (b'\x4d\x3c\xb2\xa1',b'\xa1\xb2\x3c\x4d') else 10**6
            while h:=f.read(16):
                if len(h)!=16: raise ValueError('Truncated PCAP packet header')
                sec,frac,cap,orig=struct.unpack(end+'IIII',h)
                if cap>MAX_BLOCK or cap>orig: raise ValueError('Invalid PCAP packet length')
                packet=exact_read(f,cap); digest.update(h+packet); total+=1
                t=Fraction(sec)+Fraction(frac,scale); first=t if first is None else min(first,t); last=t if last is None else max(last,t)
                key=(sec,frac,hashlib.sha256(packet).digest())
                if key in seen:
                    duplicates+=1
                    if remove: continue
                seen.add(key); out.write(h+packet); kept+=1
        elif magic==b'\x0a\x0d\x0d\x0a':
            end=None; section=-1; interfaces=[]
            while h:=f.read(8):
                if len(h)!=8: raise ValueError('Truncated PCAPNG header')
                prefix=b''
                if h[:4]==magic:
                    prefix=exact_read(f,4)
                    if prefix==b'\x4d\x3c\x2b\x1a': end='<'
                    elif prefix==b'\x1a\x2b\x3c\x4d': end='>'
                    else: raise ValueError('Invalid PCAPNG byte order')
                    section+=1; interfaces=[]
                if end is None: raise ValueError('Missing section header')
                typ,n=struct.unpack(end+'II',h)
                if n<(28 if typ==0x0a0d0d0a else 12) or n%4 or n>MAX_BLOCK: raise ValueError('Invalid PCAPNG block length')
                tail=exact_read(f,n-8-len(prefix)); block=h+prefix+tail; digest.update(block)
                if int.from_bytes(tail[-4:],'little' if end=='<' else 'big')!=n: raise ValueError('PCAPNG trailer mismatch')
                body=prefix+tail[:-4]
                if typ==1:
                    if len(body)<8: raise ValueError('Invalid interface description')
                    res=Fraction(1,10**6); offset=0; pos=8
                    while pos+4<=len(body):
                        code,length=struct.unpack(end+'HH',body[pos:pos+4]); v=body[pos+4:pos+4+length]
                        if len(v)!=length: raise ValueError('Truncated interface option')
                        if code==9 and len(v)==1: res=Fraction(1,2**(v[0]&127) if v[0]&128 else 10**v[0])
                        if code==14 and len(v)==8: offset=struct.unpack(end+'q',v)[0]
                        pos+=4+(length+3)//4*4
                        if code==0: break
                    interfaces.append((res,offset))
                elif typ==6:
                    if len(body)<20: raise ValueError('Invalid Enhanced Packet Block')
                    iid,hi,lo,cap,orig=struct.unpack(end+'IIIII',body[:20])
                    if iid>=len(interfaces) or cap>orig or 20+(cap+3)//4*4>len(body): raise ValueError('Invalid packet/interface')
                    packet=body[20:20+cap]; total+=1; res,off=interfaces[iid]; t=((hi<<32)+lo)*res+off
                    first=t if first is None else min(first,t); last=t if last is None else max(last,t)
                    key=(section,iid,hi,lo,hashlib.sha256(packet).digest())
                    if key in seen:
                        duplicates+=1
                        if remove: continue
                    seen.add(key); kept+=1
                elif typ in (2,3): raise ValueError('Legacy/Simple Packet Blocks unsupported; convert to Enhanced Packet Blocks first')
                elif typ==5: continue # omit stale interface statistics in derivative
                if typ==0x0a0d0d0a:
                    block=bytearray(block); block[16:24]=struct.pack(end+'q',-1)
                out.write(block)
        else: raise ValueError('Only uncompressed PCAP and PCAPNG are supported')
    return dict(original_packets=total,analysed_packets=kept,exact_duplicates=duplicates,
                first=float(first) if first is not None else None,last=float(last) if last is not None else None,
                sha256=digest.hexdigest())
