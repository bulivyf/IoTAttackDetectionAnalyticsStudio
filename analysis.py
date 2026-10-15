"""Bounded local operations; no model-generated Python or SQL execution."""
import json,math
import numpy as np
import pandas as pd
from data import filter_frame

OPERATIONS=['preview','summary','aggregate','timeseries','correlation','linear_model','rate_model','robust_anomaly']

def clean_records(df):return json.loads(df.to_json(orient='records',date_format='iso'))
def number(value):return float(value) if np.isfinite(value) else None

def execute(tables,spec,global_filters=None):
    tid=spec.get('table')
    if tid not in tables:raise ValueError('Choose a selected table ID from the catalog')
    t=tables[tid];df=filter_frame(t.frame,(global_filters or {}).get(tid,[]));scope_rows=len(df)
    join_metadata=None
    if spec.get('join_table'):
        right_id=spec['join_table'];key=spec.get('join_key');how=spec.get('join_how','left')
        if right_id not in tables:raise ValueError('Join table must be selected in the catalog')
        if how not in ['left','inner']:raise ValueError('Join type must be left or inner')
        right=tables[right_id];rdf=filter_frame(right.frame,(global_filters or {}).get(right_id,[]))
        if key not in df or key not in rdf:raise ValueError('Join key must exist in both tables')
        if df[key].isna().any() or rdf[key].isna().any():raise ValueError('Null join keys are ambiguous; filter them out explicitly')
        if rdf[key].duplicated().any():raise ValueError('Right join key is not unique; aggregate it first or choose a different table. Many-to-many joins are blocked.')
        renamed=rdf.rename(columns={c:'right__'+c for c in rdf if c!=key})
        df=df.merge(renamed,on=key,how=how,validate='many_to_one')
        join_metadata=dict(table=right_id,source=right.source,sha256=right.sha256,key=key,how=how,right_scope_filters=(global_filters or {}).get(right_id,[]),right_scope_rows=len(rdf))
    df=filter_frame(df,spec.get('filters',[]));op=spec.get('operation','summary')
    if op not in OPERATIONS:raise ValueError('Unsupported operation')
    limit=max(1,min(int(spec.get('limit',100)),500));x=spec.get('x');y=spec.get('y');group=spec.get('group_by',[])
    if isinstance(group,str):group=[group]
    if len(group)>4:raise ValueError('At most four grouping columns')
    for col in [c for c in [x,y]+group if c]:
        if col not in df:raise ValueError(f'Unknown column: {col}')
    result=dict(table=tid,source=t.source,sha256=t.sha256,operation=op,total_rows=len(t.frame),scope_rows=scope_rows,filtered_rows=len(df),filters=(global_filters or {}).get(tid,[])+spec.get('filters',[]),notes=list(t.notes),formula=None,model=None)
    if join_metadata:
        result['join']=join_metadata
        result['notes'].append('Validated many-to-one join. Right-table columns carry right__ prefix. Join attaches metadata; it does not establish causality.')
    out=pd.DataFrame();chart={};freq=spec.get('frequency','5min')
    allowed=['5s','30s','1min','5min','15min','1h','1D']
    if freq not in allowed:raise ValueError('Unsupported time-bin frequency')
    agg=spec.get('aggregation','sum')
    if agg not in ['sum','mean','median','min','max','count']:raise ValueError('Unsupported aggregation')
    if op=='preview':out=df.head(limit)
    elif op=='summary':
        out=pd.DataFrame([dict(column=c,dtype=str(df[c].dtype),missing=int(df[c].isna().sum()),distinct=int(df[c].nunique(dropna=False)),minimum=number(pd.to_numeric(df[c],errors='coerce').min()) if pd.api.types.is_numeric_dtype(df[c]) else None,maximum=number(pd.to_numeric(df[c],errors='coerce').max()) if pd.api.types.is_numeric_dtype(df[c]) else None) for c in df])
    elif op=='aggregate':
        if not group:raise ValueError('aggregate requires group_by')
        if y:
            temp=df[group+[y]].copy();temp[y]=pd.to_numeric(temp[y],errors='coerce')
            if agg=='sum':out=temp.groupby(group,dropna=False)[y].sum(min_count=1).reset_index(name='value')
            else:out=temp.groupby(group,dropna=False)[y].agg(agg).reset_index(name='value')
        else:out=df.groupby(group,dropna=False).size().reset_index(name='value')
        out=out.sort_values('value',ascending=False);chart=dict(kind='bar',x=group[0],y='value',color=group[1] if len(group)>1 else None)
    elif op=='timeseries':
        if not x:raise ValueError('timeseries requires timestamp column x')
        unit=spec.get('time_unit','text')
        if unit not in ['text','s','ms','us','ns']:raise ValueError('Invalid time unit')
        times=pd.to_datetime(df[x],utc=True,errors='coerce',format='mixed') if unit=='text' else pd.to_datetime(pd.to_numeric(df[x],errors='coerce'),unit=unit,utc=True,errors='coerce')
        temp=df.copy();temp['_time']=times.dt.floor(freq);result['invalid_times']=int(times.isna().sum());temp=temp.dropna(subset=['_time'])
        keys=['_time']+group
        if y:
            temp[y]=pd.to_numeric(temp[y],errors='coerce')
            out=(temp.groupby(keys)[y].sum(min_count=1) if agg=='sum' else temp.groupby(keys)[y].agg(agg)).reset_index(name='value')
        else:out=temp.groupby(keys).size().reset_index(name='value')
        out=out.sort_values('_time');chart=dict(kind='line',x='_time',y='value',color=group[0] if group else None)
        result['notes'].append('Occupied bins only. Missing bins are unknown coverage. Lines do not establish continuous monitoring.')
        result['formula']=r'N_b=\sum_i\mathbf{1}(t_i\in b),\qquad r_b=N_b/\Delta t'
        result['notes'].append('Formula describes record counts; when summing a supplied packet column, use packet totals instead. Existing coarse bins cannot be resolved into finer packet times.')
    elif op=='correlation':
        columns=spec.get('columns') or [x,y]
        if len(columns)<2 or len(columns)>12 or any(c not in df for c in columns):raise ValueError('Select 2–12 existing numeric columns')
        numeric=df[columns].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
        corr=numeric.corr(min_periods=3);out=corr.reset_index(names='column');chart=dict(kind='heatmap')
        result['formula']=r'r_{xy}=\frac{\sum_i(x_i-\bar x)(y_i-\bar y)}{\sqrt{\sum_i(x_i-\bar x)^2\sum_i(y_i-\bar y)^2}}'
        result['notes'].append('Pairwise Pearson correlation is descriptive, not causation; autocorrelation and repeated records affect interpretation.')
    elif op=='linear_model':
        if not x or not y or x==y:raise ValueError('Choose different numeric x and y columns')
        numeric=df[[x,y]].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
        if len(numeric)<3 or numeric[x].nunique()<2:raise ValueError('Need ≥3 valid pairs and varying x')
        xx=numeric[x].to_numpy();yy=numeric[y].to_numpy();xm=xx.mean();ym=yy.mean()
        slope=float(np.dot(xx-xm,yy-ym)/np.dot(xx-xm,xx-xm));intercept=float(ym-slope*xm);pred=intercept+slope*xx;res=yy-pred
        sst=float(np.sum((yy-ym)**2));sse=float(np.sum(res**2));r2=1-sse/sst if sst>0 else None
        out=pd.DataFrame({x:xx,y:yy,'prediction':pred,'residual':res}).sort_values(x)
        result['model']=dict(type='ordinary_least_squares',n=len(numeric),slope=slope,intercept=intercept,r_squared=r2,rmse=float(np.sqrt(np.mean(res**2))),fit_scope='In-sample descriptive fit; no held-out validation')
        result['formula']=rf'\hat y={intercept:.6g}+({slope:.6g})x'
        result['notes'].append('OLS assumes a useful linear relation; residual dependence/outliers/confounding can invalidate inference. R² is not confidence of validity. No causal or predictive validation supplied.')
        chart=dict(kind='regression',x=x,y=y)
    elif op=='rate_model':
        if not y:raise ValueError('Choose nonnegative event/packet count column y')
        duration=float(spec.get('exposure_seconds',0))
        if not math.isfinite(duration) or duration<=0:raise ValueError('Specify positive independently verified observed exposure_seconds; calendar span is not coverage')
        vals=pd.to_numeric(df[y],errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
        if vals.empty or (vals<0).any() or not np.allclose(vals,np.round(vals)):raise ValueError('Rate model needs nonnegative integer counts')
        total=float(vals.sum());rate=total/duration
        result['model']=dict(type='constant_rate_candidate',count=total,exposure_seconds=duration,rate_per_second=rate,poisson_assumption='Independent events and constant rate; not tested. Flood packets are often dependent.')
        result['formula']=r'\hat\lambda=\frac{N}{T},\qquad P(N_t=k)=\frac{(\lambda t)^ke^{-\lambda t}}{k!}'
        out=pd.DataFrame([dict(count=total,observed_seconds=duration,rate_per_second=rate)])
        result['notes'].append('A rate of packets is not a rate of attacks. Overdispersion, duplicate input and uncertain coverage invalidate a Poisson incident interpretation.')
    elif op=='robust_anomaly':
        if not y:raise ValueError('Choose numeric y column')
        vals=pd.to_numeric(df[y],errors='coerce').replace([np.inf,-np.inf],np.nan);valid=vals.dropna()
        if len(valid)<5:raise ValueError('Need at least five numeric observations')
        median=float(valid.median());mad=float((valid-median).abs().median());threshold=float(spec.get('threshold',3.5))
        if not math.isfinite(threshold) or threshold<=0:raise ValueError('Threshold must be positive')
        if mad==0:raise ValueError('MAD is zero; robust z-score is undefined. Choose another variable or a documented baseline.')
        out=df.copy();out['robust_z']=0.67448975*(vals-median)/mad;out['flag']=out.robust_z.abs()>threshold
        result['model']=dict(type='descriptive_robust_score',median=median,mad=mad,threshold=threshold,flagged=int(out.flag.sum()),valid_observations=len(valid))
        result['formula']=r'z_i^{\mathrm{robust}}=0.67449\frac{x_i-\operatorname{median}(x)}{\operatorname{MAD}(x)}'
        result['notes'].append('Exploratory within-selection outliers, not independently trained attack detections or probabilities. Use a separate normal baseline for detection research.')
        out=out.reindex(out.robust_z.abs().sort_values(ascending=False).index);chart=dict(kind='bar',x=x or out.columns[0],y='robust_z',color='flag')
    result['result_rows']=len(out);result['display_truncated']=len(out)>limit
    result['rows']=clean_records(out.head(limit));result['chart']=chart;result['spec']=spec
    return result,out.head(min(limit,500)).copy()
