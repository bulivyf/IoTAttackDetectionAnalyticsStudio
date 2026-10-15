"""Streaming, disk-backed exact deduplication and time-local packet observations."""
import hashlib,json,sqlite3,math,struct,os
from pathlib import Path
from collections import Counter
import pandas as pd
from timeline_engine import packets,endpoints,filename_time
from capture_filters import capture_tags
from rules import OUI,PRIORS,scope

VERSION='studio-1'

def transport(link,data):
    offset={1:14,113:16,276:20,101:0,228:0,229:0}.get(link)
    if offset is None:return 0,0,b'',0
    if link==1:
        typ=int.from_bytes(data[12:14],'big')
        while typ in (0x8100,0x88a8):
            typ=int.from_bytes(data[offset+2:offset+4],'big');offset+=4
    b=data[offset:]
    if not b:return 0,0,b'',0
    if b[0]>>4==4 and len(b)>=20:
        if int.from_bytes(b[6:8],'big')&0x1fff:return 0,0,b'',0
        proto=b[9];b=b[(b[0]&15)*4:]
    elif b[0]>>4==6 and len(b)>=40:proto=b[6];b=b[40:]
    else:return 0,0,b'',0
    if proto==6 and len(b)>=20:
        return int.from_bytes(b[:2],'big'),int.from_bytes(b[2:4],'big'),b[(b[12]>>4)*4:],b[13]
    if proto==17 and len(b)>=8:return int.from_bytes(b[:2],'big'),int.from_bytes(b[2:4],'big'),b[8:],0
    return 0,0,b'',0

def message(sp,dp,payload,proto,flags):
    activity='';topic='';purpose='Unresolved';score=0
    if proto=='ARP':return 'ARP claim/request','','Address resolution',90
    if 1883 in (sp,dp):
        activity='MQTT port traffic (frame unresolved)'
        if len(payload)>2:
            kind=payload[0]>>4;names={1:'CONNECT',2:'CONNACK',3:'PUBLISH',8:'SUBSCRIBE',9:'SUBACK',12:'PINGREQ',13:'PINGRESP',14:'DISCONNECT'}
            activity='MQTT '+names.get(kind,str(kind))+' candidate'
            if kind==3:
                i=1
                while i<len(payload) and i<=4:
                    v=payload[i];i+=1
                    if v<128:break
                if i+2<=len(payload):
                    n=int.from_bytes(payload[i:i+2],'big')
                    if n and i+2+n<=len(payload):topic=payload[i+2:i+2+n].decode('utf8','replace')[:160]
    elif 8883 in (sp,dp):activity='Encrypted MQTT port candidate'
    elif 5683 in (sp,dp):activity='CoAP port traffic'
    elif 53 in (sp,dp):activity='DNS port traffic'
    elif {sp,dp} & {67,68}:activity='DHCP port traffic (lease not decoded)'
    elif 443 in (sp,dp):activity='TLS/HTTPS port candidate'
    elif 80 in (sp,dp):activity='HTTP port candidate'
    elif proto=='TCP' and flags&2:activity='TCP SYN+ACK' if flags&16 else 'TCP SYN'
    else:activity=proto+' traffic'
    lower=topic.lower()
    for tokens,role in [(('moist','soil'),'Soil/moisture messaging'),(('temp','heat'),'Temperature messaging'),(('humid',),'Humidity messaging'),(('light','ldr'),'Light messaging'),(('buzzer','alarm'),'Alarm/feedback messaging'),(('pressure','baro'),'Pressure messaging')]:
        if any(t in lower for t in tokens):purpose=role;score=70;break
    return activity,topic,purpose,score

def manifest(paths,zone):
    return hashlib.sha256(json.dumps([VERSION,zone,[(str(p.resolve()),p.stat().st_size,p.stat().st_mtime_ns) for p in paths]]).encode()).hexdigest()

def build(paths,destination,zone='UTC',progress=None):
    paths=sorted(map(Path,paths));dest=Path(destination);dest.parent.mkdir(parents=True,exist_ok=True)
    tmp=dest.with_suffix('.building.sqlite');tmp.unlink(missing_ok=True)
    db=sqlite3.connect(tmp)
    db.executescript('''PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
    CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
    CREATE TABLE seen(fingerprint BLOB PRIMARY KEY,category TEXT) WITHOUT ROWID;
    CREATE TABLE observations(time INTEGER,filename_clock INTEGER,category TEXT,source TEXT,destination TEXT,source_mac TEXT,destination_mac TEXT,protocol TEXT,source_port INTEGER,destination_port INTEGER,activity TEXT,topic TEXT,purpose TEXT,purpose_score INTEGER,packets INTEGER,bytes INTEGER);
    CREATE TABLE captures(file TEXT,category TEXT,filename_start REAL,packet_start REAL,packet_end REAL,original_packets INTEGER,retained_packets INTEGER,duplicate_packets INTEGER,conflicting_duplicate_labels INTEGER,unmapped_packets INTEGER,sha256 TEXT);
    ''')
    try:
        for n,path in enumerate(paths):
            if progress:progress(n/len(paths),path.name)
            category=capture_tags(path)[1];nominal=filename_time(path,zone)
            digest=hashlib.sha256()
            with path.open('rb') as f:
                while chunk:=f.read(1024*1024):digest.update(chunk)
            counts=Counter();bytes_=Counter();total=kept=duplicates=conflicts=unmapped=0;first=last=anchor=None
            for exact,iface,link,data,wire in packets(path):
                total+=1;t=float(exact)
                if anchor is None:anchor=t
                first=t if first is None else min(first,t);last=t if last is None else max(last,t)
                # Scope retains link/interface index. Exact time and packet bytes avoid collapsing real retransmissions.
                h=hashlib.sha256(str((exact.numerator,exact.denominator,link,iface,wire)).encode()+data).digest()
                try:db.execute('INSERT INTO seen VALUES (?,?)',(h,category))
                except sqlite3.IntegrityError:
                    duplicates+=1
                    previous=db.execute('SELECT category FROM seen WHERE fingerprint=?',(h,)).fetchone()[0]
                    conflicts+=previous!=category
                    continue
                kept+=1;ep=endpoints(link,data)
                if not ep:unmapped+=1;continue
                src,dst,sm,dm,proto=ep
                sp,dp,payload,flags=transport(link,data);activity,topic,purpose,score=message(sp,dp,payload,proto,flags)
                actual=int(t//5)*5;ft=int(((nominal+t-anchor) if nominal is not None else t)//5)*5
                k=(actual,ft,category,src,dst,sm,dm,proto,sp,dp,activity,topic,purpose,score)
                counts[k]+=1;bytes_[k]+=wire
                if total%50000==0:
                    db.executemany('INSERT INTO observations VALUES ('+','.join(['?']*16)+')',[(*k,v,bytes_[k]) for k,v in counts.items()]);counts.clear();bytes_.clear()
                    if progress:progress(n/len(paths),f'{path.name}: {total:,} packets')
            db.executemany('INSERT INTO observations VALUES ('+','.join(['?']*16)+')',[(*k,v,bytes_[k]) for k,v in counts.items()])
            db.execute('INSERT INTO captures VALUES ('+','.join(['?']*11)+')',(str(path),category,nominal,first,last,total,kept,duplicates,conflicts,unmapped,digest.hexdigest()));db.commit()
        db.execute('INSERT INTO meta VALUES (?,?)',('manifest',manifest(paths,zone)))
        db.execute('INSERT INTO meta VALUES (?,?)',('filename_timezone',zone))
        db.executescript('CREATE INDEX actual_time ON observations(time);CREATE INDEX nominal_time ON observations(filename_clock);DROP TABLE seen;')
        db.commit();db.close();os.replace(tmp,dest)
    except BaseException:
        db.close();tmp.unlink(missing_ok=True);raise
    return dest

def read(dbpath,sql,args=()):
    with sqlite3.connect(dbpath) as db:return pd.read_sql_query(sql,db,params=args)

def selected(dbpath,start,end,categories,clock='time'):
    assert clock in ('time','filename_clock')
    if not categories:return read(dbpath,'SELECT * FROM observations WHERE 0')
    return read(dbpath,f'SELECT * FROM observations WHERE {clock}>=? AND {clock}<? AND category IN ({",".join("?" for _ in categories)})',(start,end,*categories))

def identities(frame):
    rows=[]
    if frame.empty:return pd.DataFrame(columns=['ip','mac','association','packets','hardware','hardware_score','role','role_score','scope'])
    for side in ['source','destination']:
        for (ip,mac,proto),g in frame.groupby([side,side+'_mac','protocol'],dropna=False):
            if not mac or mac=='00:00:00:00:00:00' or int(mac[:2],16)&1:continue
            association=('ARP sender claim' if side=='source' else 'ARP target field') if proto=='ARP' else 'Ethernet '+side+' association'
            hw,score=OUI.get(mac[:8],('Unknown hardware',0))
            if int(mac[:2],16)&2:hw,score='Locally administered interface; hardware unknown',0
            private=scope(ip)=='Local/private'
            if not private:hw,score='Remote hardware not observable from local MAC',0
            role='Unresolved';rc=0
            for prior in PRIORS.values():
                if private and mac==prior[0] and side=='source' and proto!='ARP':role,rc=prior[3],min(prior[4],75)
            if side=='destination' and proto!='ARP':score=min(score,40);role='Next-hop association; ownership unverified';rc=0
            if proto=='ARP':score=min(score,40);role='Claimed address; ownership unverified';rc=0
            rows.append(dict(ip=ip,mac=mac,association=association,packets=int(g.packets.sum()),hardware=hw,hardware_score=score,role=role,role_score=rc,scope=scope(ip)))
    return pd.DataFrame(rows).drop_duplicates() if rows else identities(frame.iloc[:0])
