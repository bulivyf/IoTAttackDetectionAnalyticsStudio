"""Compact event navigation: episode starts clustered only for rendering."""
import pandas as pd
import plotly.graph_objects as go

def event_starts(summary):
    starts=[]
    for category,g in summary.groupby('category'):
        g=g.sort_values('t')
        for r in g.loc[g.t.diff().isna()|g.t.diff().gt(60)].itertuples():
            starts.append((int(r.t),category))
    return sorted(starts)

def event_rail(summary,start,end,lo,hi,max_marks=100):
    events=event_starts(summary)
    width=max(60,(hi-lo)/max_marks)
    groups={}
    for t,cat in events:groups.setdefault(int((t-lo)//width),[]).append((t,cat))
    x=[];custom=[];hover=[];colors=[]
    for values in groups.values():
        t=values[0][0];cats=sorted({c for _,c in values})
        x.append(pd.to_datetime(t,unit='s',utc=True));custom.append([t])
        hover.append(f'{len(values)} activity start(s)<br>'+', '.join(cats)+'<br>'+pd.to_datetime(t,unit='s',utc=True).strftime('%d %b %Y %H:%M UTC'))
        colors.append('#ed887e' if any(c not in ('Normal','Unclassified') for c in cats) else '#85bdde')
    fig=go.Figure(go.Scatter(x=x,y=[0]*len(x),customdata=custom,hovertext=hover,hoverinfo='text',mode='markers',marker=dict(symbol='line-ns',size=13,color=colors,line=dict(width=3,color=colors)),selected=dict(marker=dict(opacity=1)),unselected=dict(marker=dict(opacity=.8))))
    fig.add_vrect(x0=pd.to_datetime(start,unit='s',utc=True),x1=pd.to_datetime(end,unit='s',utc=True),fillcolor='white',opacity=.18,line_width=0)
    fig.update_layout(height=78,margin=dict(l=10,r=10,t=2,b=25),template='plotly_dark',showlegend=False,clickmode='event+select',xaxis=dict(range=[pd.to_datetime(lo,unit='s',utc=True),pd.to_datetime(hi,unit='s',utc=True)],tickformat='%d %b %H:%M',fixedrange=True),yaxis=dict(visible=False,fixedrange=True,range=[-1,1]),paper_bgcolor='#0e1624',plot_bgcolor='#0e1624')
    return fig
