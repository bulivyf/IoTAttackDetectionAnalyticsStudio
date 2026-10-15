"""Capture-driven timeline. Dataset labels are provenance, not detected attacks."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib,ipaddress,math,re,struct
import pandas as pd
from capture_filters import capture_tags
from capture_io import exact_read,MAX_BLOCK

ICONS={'Normal':'🟢','Arp_Spoofing':'🔀','BotNet_DDOS':'🤖','HTTP_Flood':'🌐','ICMP_Flood':'📡','MQTT_Flood':'📨','Port_Scanning':'🔎','TCP_Flood':'🔗','UDP_Flood':'💧','Unclassified':'❔'}

def filename_time(path,zone='UTC'):
    stem=Path(path).stem
    patterns=[(r'(?<!\d)(20\d{12})(?!\d)','%Y%m%d%H%M%S'),
              (r'(20\d{2}-\d{2}-\d{2}[T_ ]\d{2}[-:]\d{2}[-:]\d{2})',None),
              (r'(?<!\d)(20\d{6})[_-](\d{6})(?!\d)','compact')]
    for pattern,fmt in patterns:
        m=re.search(pattern,stem)
        if not m: continue
        try:
            if fmt=='compact': dt=datetime.strptime(m[1]+m[2],'%Y%m%d%H%M%S')
            elif fmt: dt=datetime.strptime(m[1],fmt)
            else:
                v=m[1]; dt=datetime.strptime(v[:10]+' '+v[11:].replace('-',':'),'%Y-%m-%d %H:%M:%S')
            return dt.replace(tzinfo=ZoneInfo(zone)).timestamp()
        except ValueError: pass
    return None

def packets(path):
    """Yield exact time, interface scope, link type, captured bytes, wire length."""
    with open(path,'rb') as f:
        magic=exact_read(f,4);f.seek(0)
        if magic in (b'\xd4\xc3\xb2\xa1',b'\xa1\xb2\xc3\xd4',b'\x4d\x3c\xb2\xa1',b'\xa1\xb2\x3c\x4d'):
            h=exact_read(f,24);end='<' if magic in (b'\xd4\xc3\xb2\xa1',b'\x4d\x3c\xb2\xa1') else '>'
            scale=10**9 if magic in (b'\x4d\x3c\xb2\xa1',b'\xa1\xb2\x3c\x4d') else 10**6
            link=struct.unpack(end+'I',h[20:24])[0]&65535
            while h:=f.read(16):
                if len(h)!=16:raise ValueError('Truncated packet header')
                sec,frac,cap,orig=struct.unpack(end+'IIII',h)
                if cap>MAX_BLOCK or cap>orig:raise ValueError('Invalid packet length')
                yield Fraction(sec)+Fraction(frac,scale),(0,0),link,exact_read(f,cap),orig
        elif magic==b'\x0a\x0d\x0d\x0a':
            end=None;section=-1;interfaces=[]
            while h:=f.read(8):
                if len(h)!=8:raise ValueError('Truncated block')
                prefix=b''
                if h[:4]==magic:
                    prefix=exact_read(f,4)
                    if prefix==b'\x4d\x3c\x2b\x1a':end='<'
                    elif prefix==b'\x1a\x2b\x3c\x4d':end='>'
                    else:raise ValueError('Invalid byte order')
                    section+=1;interfaces=[]
                if end is None:raise ValueError('No section header')
                typ,n=struct.unpack(end+'II',h)
                if n<(28 if typ==0x0a0d0d0a else 12) or n%4 or n>MAX_BLOCK:raise ValueError('Invalid block length')
                tail=exact_read(f,n-8-len(prefix))
                if struct.unpack(end+'I',tail[-4:])[0]!=n:raise ValueError('Invalid trailer')
                body=prefix+tail[:-4]
                if typ==1:
                    if len(body)<8:raise ValueError('Invalid interface')
                    link=struct.unpack(end+'H',body[:2])[0];res=Fraction(1,10**6);offset=0;pos=8
                    while pos+4<=len(body):
                        c,l=struct.unpack(end+'HH',body[pos:pos+4]);v=body[pos+4:pos+4+l]
                        if len(v)!=l:raise ValueError('Invalid interface option')
                        if c==9 and len(v)==1:res=Fraction(1,2**(v[0]&127) if v[0]&128 else 10**v[0])
                        if c==14 and len(v)==8:offset=struct.unpack(end+'q',v)[0]
                        pos+=4+(l+3)//4*4
                        if c==0:break
                    interfaces.append((link,res,offset))
                elif typ==6:
                    if len(body)<20:raise ValueError('Invalid packet block')
                    iid,hi,lo,cap,orig=struct.unpack(end+'IIIII',body[:20])
                    if iid>=len(interfaces) or cap>orig or 20+(cap+3)//4*4>len(body):raise ValueError('Invalid packet/interface')
                    link,res,offset=interfaces[iid]
                    yield ((hi<<32)+lo)*res+offset,(section,iid),link,body[20:20+cap],orig
                elif typ in (2,3):raise ValueError('Untimed/legacy packet block unsupported')
        else:raise ValueError('Only uncompressed PCAP and PCAPNG supported')

def endpoints(link,data):
    sm=dm='';offset=0;ethertype=None
    if link==1:
        if len(data)<14:return None
        dm=':'.join(f'{b:02x}' for b in data[:6]);sm=':'.join(f'{b:02x}' for b in data[6:12]);ethertype=int.from_bytes(data[12:14],'big');offset=14
        while ethertype in (0x8100,0x88a8):
            if len(data)<offset+4:return None
            ethertype=int.from_bytes(data[offset+2:offset+4],'big');offset+=4
    elif link==113:
        if len(data)<16:return None
        ethertype=int.from_bytes(data[14:16],'big');offset=16
    elif link==276:
        if len(data)<20:return None
        ethertype=int.from_bytes(data[:2],'big');offset=20
    elif link in (101,228,229):offset=0
    else:return None
    b=data[offset:]
    if ethertype==0x806 and len(b)>=28 and b[4:6]==b'\x06\x04':
        asm=':'.join(f'{v:02x}' for v in b[8:14]);adm=':'.join(f'{v:02x}' for v in b[18:24]) if any(b[18:24]) else ''
        return str(ipaddress.ip_address(b[14:18])),str(ipaddress.ip_address(b[24:28])),asm,adm,'ARP'
    if not b:return None
    if b[0]>>4==4 and len(b)>=20:return str(ipaddress.ip_address(b[12:16])),str(ipaddress.ip_address(b[16:20])),sm,dm,{6:'TCP',17:'UDP',1:'ICMP'}.get(b[9],'IPv4')
    if b[0]>>4==6 and len(b)>=40:return str(ipaddress.ip_address(b[8:24])),str(ipaddress.ip_address(b[24:40])),sm,dm,'IPv6'
    return None

def build_timeline(paths,zone='UTC',dedup=True,resolution=5,progress=None):
    counts=Counter();bytecounts=Counter();captures=[];nodes=defaultdict(set);warnings=[];whole_hashes=set()
    for index,path in enumerate(paths):
        path=Path(path);month,category=capture_tags(path);ft=filename_time(path,zone)
        if progress:progress(f'Indexing {index+1}/{len(paths)}: {path.name}',index/max(1,len(paths)))
        digest=hashlib.sha256()
        with path.open('rb') as f:
            while chunk:=f.read(1024*1024):digest.update(chunk)
        filehash=digest.hexdigest()
        if filehash in whole_hashes:
            warnings.append(f'Skipped identical whole-file content: {path}');continue
        whole_hashes.add(filehash)
        seen=set();original=duplicates=kept=unsupported=0;first=last=anchor=None;local=Counter();localbytes=Counter()
        for exact,iface,link,data,wire in packets(path):
            original+=1;t=float(exact)
            if anchor is None:anchor=t
            first=t if first is None else min(first,t);last=t if last is None else max(last,t)
            key=(iface,exact,hashlib.sha256(data).digest())
            if key in seen:
                duplicates+=1
                if dedup:continue
            seen.add(key);kept+=1
            ep=endpoints(link,data)
            if not ep:unsupported+=1;continue
            src,dst,sm,dm,proto=ep
            if sm and sm not in ['00:00:00:00:00:00','ff:ff:ff:ff:ff:ff']:nodes[src].add(sm)
            if dm and dm not in ['00:00:00:00:00:00','ff:ff:ff:ff:ff:ff']:nodes[dst].add(dm)
            actual=math.floor(t/resolution)*resolution
            nominal=math.floor((ft+t-anchor)/resolution)*resolution if ft is not None else actual
            k=(actual,nominal,category,src,dst)
            local[k]+=1;localbytes[k]+=wire
        if first is not None:
            captures.append(dict(file=str(path),folder_month=month,category=category,filename_time=ft,packet_start=first,packet_end=last,
             original_packets=original,exact_duplicates=duplicates,retained_packets=kept,unmapped_packets=unsupported,
             time_offset_seconds=None if ft is None else ft-anchor))
            if month!='Unspecified month' and datetime.fromtimestamp(first,timezone.utc).strftime('%m_%Y')!=month:
                warnings.append(f'{path.name}: folder month {month} differs from packet date {datetime.fromtimestamp(first,timezone.utc).date()}')
            if ft is None:warnings.append(f'{path.name}: no recognised filename timestamp; filename timeline falls back to packet time')
            elif abs(ft-anchor)>60:warnings.append(f'{path.name}: filename and first packet differ by {ft-anchor:,.1f} seconds')
            if anchor!=first:warnings.append(f'{path.name}: internally unordered; filename alignment uses first encountered packet')
        counts.update(local);bytecounts.update(localbytes)
    if progress:progress('Timeline index ready',1.0)
    return dict(version='timeline-1.0',resolution=resolution,filename_timezone=zone,dedup=dedup,
        captures=captures,nodes={ip:sorted(m) for ip,m in nodes.items()},warnings=warnings,
        bins=[dict(packet_time=k[0],filename_time=k[1],category=k[2],source=k[3],destination=k[4],packets=v,wire_bytes=bytecounts[k]) for k,v in counts.items()])

def episode_proxies(bins,gap,resolution=5):
    """Split same label/source/destination after missing activity exceeds gap."""
    if bins.empty:return pd.DataFrame(columns=['category','source','destination','start','end','packets'])
    d=bins[~bins.category.isin(['Normal','Unclassified'])].groupby(['category','source','destination','time'],as_index=False).packets.sum().sort_values(['category','source','destination','time'])
    if d.empty:return pd.DataFrame(columns=['category','source','destination','start','end','packets'])
    breaks=d.groupby(['category','source','destination']).time.diff().gt(gap+resolution) | d.groupby(['category','source','destination']).time.diff().isna()
    d['episode']=breaks.cumsum()
    e=d.groupby(['episode','category','source','destination'],as_index=False).agg(start=('time','min'),end=('time','max'),packets=('packets','sum'))
    e['end']+=resolution
    return e
