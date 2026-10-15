import json,re,zipfile,io
import pandas as pd
from display_time import readable_frame,is_time_column,as_datetime
import plotly.express as px
import plotly.graph_objects as go

def figure(result):
    df=pd.DataFrame(result['rows']);c=result.get('chart',{})
    if df.empty or not c:return None
    kind=c.get('kind');x=c.get('x');y=c.get('y');color=c.get('color')
    if kind not in ['heatmap'] and x in df and is_time_column(x):df[x]=as_datetime(df[x])
    if kind=='bar':fig=px.bar(df,x=x,y=y,color=color)
    elif kind=='line':
        df[x]=pd.to_datetime(df[x],utc=True,errors='coerce');fig=px.line(df.sort_values(x),x=x,y=y,color=color,markers=True)
    elif kind=='heatmap':
        matrix=df.set_index('column');fig=px.imshow(matrix.astype(float),zmin=-1,zmax=1,color_continuous_scale='RdBu_r',aspect='auto')
    elif kind=='regression':
        fig=px.scatter(df,x=x,y=y)
        fig.add_trace(go.Scatter(x=df[x],y=df.prediction,mode='lines',name='OLS fitted line'))
    else:return None
    if x and is_time_column(x):fig.update_xaxes(title_text=x+' (UTC)',tickformat='%d %b %Y<br>%H:%M:%S',hoverformat='%d %b %Y, %H:%M:%S UTC')
    fig.update_layout(title=f'{result.get("id","")} · {result["operation"]} · {result["source"]}',template='plotly_dark')
    return fig

def markdown(session):
    lines=['# Farm-Flow research session','',f'Session: {session.get("title","Untitled")}', '', '## Sources and scope', '```json', json.dumps(session.get('scope',{}),indent=2), '```']
    for message in session.get('history',[]):lines+=['',f'### {message["role"].title()}',message['content']]
    for result in session.get('results',[]):
        lines+=['',f'## {result["id"]}: {result["operation"]}',f'Source: {result["source"]}; SHA-256: {result["sha256"]}',f'Rows after filters: {result["filtered_rows"]}', '```json',json.dumps(result['spec'],indent=2),'```']
        if result.get('join'):lines+=['Additional joined source: '+json.dumps(result['join'])]
        if result.get('formula'):lines+=['$$',result['formula'],'$$']
        if result.get('model'):lines+=['```json',json.dumps(result['model'],indent=2),'```']
        lines+=['Notes: '+'; '.join(result['notes'])]
    lines+=['','## Next external action',session.get('next_action',''),'','## Living e-units',json.dumps(session.get('eunits',[]),indent=2,ensure_ascii=False)]
    return '\n'.join(lines)

def bundle(session):
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('session.json',json.dumps(session,indent=2,ensure_ascii=False))
        z.writestr('research_notes.md',markdown(session))
        for result in session.get('results',[]):
            stem=re.sub(r'[^a-zA-Z0-9_-]','_',result['id'])
            z.writestr(stem+'.csv',readable_frame(pd.DataFrame(result['rows'])).to_csv(index=False))
            fig=figure(result)
            if fig is not None:z.writestr(stem+'.html',fig.to_html(include_plotlyjs=True,full_html=True))
    return data.getvalue()
