"""Local adapters with source hashes; tables never silently union overlapping exports."""
from dataclasses import dataclass
from pathlib import Path
import hashlib,json,re
import pandas as pd
from display_time import readable_frame

@dataclass
class Table:
    id:str
    name:str
    source:str
    sha256:str
    frame:pd.DataFrame
    notes:list

def records(value):
    if isinstance(value,list):return pd.json_normalize(value)
    if isinstance(value,dict):return pd.json_normalize([dict(key=k,value=v) for k,v in value.items()])
    return pd.DataFrame()

def load_bytes(name,blob,delimiter="Auto",encoding="utf-8-sig"):
    sha=hashlib.sha256(blob).hexdigest();base=Path(name).stem;tables=[]
    def add(suffix,df,notes=None):
        if df.empty:return
        df=df.copy();df.columns=df.columns.astype(str).str.strip()
        # Lists/dictionaries remain readable strings, never executable objects.
        for col in df.select_dtypes('object'):
            df[col]=df[col].map(lambda v:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v)
        tid=re.sub(r'[^a-zA-Z0-9_]','_',base+'_'+suffix)+'_'+sha[:8]
        tables.append(Table(tid,base+' / '+suffix,name,sha,df,notes or []))
    if Path(name).suffix.lower() in ['.csv','.tsv']:
        import io
        import csv
        if delimiter=='Auto':
            if name.lower().endswith('.tsv'):sep='\t'
            else:
                sample=blob[:65536].decode(encoding,errors='replace')
                try:sep=csv.Sniffer().sniff(sample,delimiters=',;\t').delimiter
                except csv.Error:sep=','
        else:sep='\t' if delimiter=='Tab' else delimiter
        df=pd.read_csv(io.BytesIO(blob),sep=sep,encoding=encoding,low_memory=False)
        add('table',df,['Full selected table loaded without sampling or row deduplication. Do not sum overlapping full/monthly/train/test/export copies.'])
    elif Path(name).suffix.lower()=='.json':
        obj=json.loads(blob)
        if isinstance(obj,dict) and 'nodes' in obj and 'captures' in obj and obj.get('version')!='timeline-1.0':
            inv=[];macs=[];clues=[];topics=[];channels=[]
            if isinstance(obj['nodes'],dict):
                for ip,n in obj['nodes'].items():
                    if not isinstance(n,dict):continue
                    inv.append({k:v for k,v in n.items() if k not in ['clues','topics','hosts','macs','channels']}|{'ip':ip})
                    for mac,v in n.get('macs',{}).items():macs.append(dict(ip=ip,mac=mac,**v))
                    for clue in n.get('clues',{}).values():clues.append(dict(ip=ip,**clue))
                    for topic,count in n.get('topics',{}).items():topics.append(dict(ip=ip,topic=topic,occurrences=count))
                    for topic,v in n.get('channels',{}).items():channels.append(dict(ip=ip,topic=topic,**v))
            add('inventory',records(inv),['IP aggregates can combine different devices across dates.'])
            add('mac_spans',records(macs),['First/last/count spans are NOT individual ARP or DHCP events. Ethernet next-hop associations do not prove IP ownership.'])
            add('evidence',records(clues),['Confidence values are heuristic designation scores, not compromise probabilities. Examples may be bounded.'])
            add('topics',records(topics));add('channels',records(channels),['Mean message spacing across gaps is not a within-session publication period.'])
            for key in ['captures','traffic','edges','samples']:
                add(key,records(obj.get(key,[])),['Capture-derived aggregates; original-plus-segment overlap may inflate counts.']+(['Payload examples may be capped at 10,000.'] if key=='samples' else []))
            meta={k:obj.get(k) for k in ['version','created','bin_seconds','deduplication','methodology','selection','limitations']}
            add('study_metadata',records([meta]));add('warnings',pd.DataFrame({'warning':obj.get('warnings',[])}))
        elif isinstance(obj,dict) and obj.get('version')=='timeline-1.0':
            for key in ['bins','captures']:add(key,records(obj.get(key,[])),['Attack categories are folder labels, not independently detected incidents.'])
        elif isinstance(obj,list):add('records',records(obj))
        elif isinstance(obj,dict):add('object',pd.json_normalize(obj))
        else:raise ValueError('JSON must contain an object or record list')
    else:raise ValueError('Supported: CSV, TSV and JSON study exports. Convert raw captures with the Observatory first.')
    return tables

def catalog(tables,scopes=None):
    result=[]
    for tid,t in tables.items():
        scoped=filter_frame(t.frame,(scopes or {}).get(tid,[]))
        sample=readable_frame(scoped.head(3))
        for c in sample:sample[c]=sample[c].map(lambda x:str(x)[:160] if isinstance(x,str) else x)
        result.append(dict(table=tid,name=t.name,source=t.source,sha256=t.sha256,rows=len(scoped),total_rows=len(t.frame),columns=[dict(name=c,dtype=str(t.frame[c].dtype)) for c in t.frame],notes=t.notes,sample=json.loads(sample.to_json(orient='records',date_format='iso'))))
    return result

def filter_frame(df,filters):
    out=df
    if not isinstance(filters,list) or len(filters)>20:raise ValueError('Use at most 20 filter clauses')
    for f in filters:
        col,op,value=f['column'],f['op'],f.get('value')
        if col not in out:raise ValueError(f'Unknown column: {col}')
        s=out[col]
        if op=='eq':mask=s.astype(str).eq(str(value))
        elif op=='ne':mask=s.astype(str).ne(str(value))
        elif op=='in':
            if not isinstance(value,list):raise ValueError('in requires a list')
            mask=s.astype(str).isin([str(v) for v in value])
        elif op=='contains':mask=s.astype(str).str.contains(str(value),case=False,regex=False,na=False)
        elif op in ['ge','le','gt','lt']:
            v=float(value);s=pd.to_numeric(s,errors='coerce');mask={'ge':s.ge,'le':s.le,'gt':s.gt,'lt':s.lt}[op](v)
        elif op in ['after','before']:
            unit=f.get('unit')
            ts=pd.to_datetime(pd.to_numeric(s,errors='coerce'),unit=unit,utc=True,errors='coerce') if unit else pd.to_datetime(s,utc=True,errors='coerce',format='mixed')
            v=pd.to_datetime(value,utc=True);mask=ts.ge(v) if op=='after' else ts.le(v)
        elif op=='not_null':mask=s.notna()
        else:raise ValueError(f'Unknown filter operation: {op}')
        out=out[mask.fillna(False)]
    return out.copy()
