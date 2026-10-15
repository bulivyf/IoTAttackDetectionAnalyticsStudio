"""Readable UTC dates. Presentation only: original numeric values are unchanged."""
import re
from pathlib import Path
import pandas as pd

BUILD='2026-10-15 · research-data-v3'
TIME_NAMES={'time','timestamp','ts','first','last','start','end','first_seen','last_seen','created','updated','utc','_time','packet_start','packet_end','packet_time','filename_time','filename_clock','filename_start','first_seen_utc','last_seen_utc'}

def is_time_column(name):
    n=str(name).strip().lower().removeprefix('right__').split('.')[-1]
    n=re.sub(r'[\s\-]+','_',n)
    n=re.sub(r'[^a-z0-9_]','',n)
    n=re.sub(r'_(unix|epoch|seconds|milliseconds|microseconds|nanoseconds|s|ms|us|ns|utc)$','',n)
    return n in TIME_NAMES or n.endswith('_timestamp')

def as_datetime(series):
    if pd.api.types.is_datetime64_any_dtype(series):return pd.to_datetime(series,utc=True,errors='coerce')
    text=series.astype('string').str.strip()
    # Support scientific notation and decimal strings, including grouping commas.
    numeric=pd.to_numeric(text.str.replace(',','',regex=False),errors='coerce')
    result=pd.Series(pd.NaT,index=series.index,dtype='datetime64[ns, UTC]')
    numeric_mask=numeric.notna()
    for unit,mask in [('ns',numeric.abs().ge(1e17)),('us',numeric.abs().ge(1e14)&numeric.abs().lt(1e17)),('ms',numeric.abs().ge(1e11)&numeric.abs().lt(1e14)),('s',numeric.abs().lt(1e11))]:
        mask=mask&numeric_mask
        if mask.any():result.loc[mask]=pd.to_datetime(numeric.loc[mask],unit=unit,utc=True,errors='coerce')
    other=~numeric_mask&text.notna()&text.ne('')
    if other.any():result.loc[other]=pd.to_datetime(text.loc[other],utc=True,errors='coerce',format='mixed')
    return result

def readable_frame(frame):
    out=frame.copy()
    for col in out:
        if is_time_column(col) or pd.api.types.is_datetime64_any_dtype(out[col]):
            parsed=as_datetime(out[col]);valid=parsed.notna()
            text=out[col].astype(object).where(out[col].notna(),'')
            text.loc[valid]=parsed.loc[valid].dt.strftime('%d %b %Y, %H:%M:%S UTC')
            # Do not silently show an undecoded epoch value in a date column.
            invalid=~valid&pd.to_numeric(out[col].astype(str).str.replace(',','',regex=False),errors='coerce').notna()
            text.loc[invalid]='Unparsed timestamp — check source format'
            out[col]=text
    if {'column','minimum','maximum'}.issubset(out.columns):
        for i,row in out.iterrows():
            if is_time_column(row['column']):
                for field in ['minimum','maximum']:
                    if pd.notna(row[field]):
                        ts=as_datetime(pd.Series([row[field]])).iloc[0]
                        if pd.notna(ts):out[field]=out[field].astype(object);out.at[i,field]=ts.strftime('%d %b %Y, %H:%M:%S UTC')
    return out

def diagnostic_panel(app_path):
    import streamlit as st
    st.sidebar.caption('Build: '+BUILD)
    with st.sidebar.expander('Date-display diagnostic'):
        sample=readable_frame(pd.DataFrame({'first':[1661245754.032132],'last':[1661246777.0]}))
        st.write('Formatter check: '+sample['first'].iloc[0])
        st.code(str(Path(app_path).resolve()),language=None)
        st.code(str(Path(__file__).resolve()),language=None)
        st.caption('The paths above identify the running app and date formatter. If the check is readable but a data column is not, provide its exact heading and app tab.')
