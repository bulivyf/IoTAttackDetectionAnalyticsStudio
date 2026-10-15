import math,io
import pandas as pd
import plotly.graph_objects as go
from timeline_engine import ICONS

def positions(ips):
    return {ip:(math.cos(2*math.pi*i/max(1,len(ips))),math.sin(2*math.pi*i/max(1,len(ips)))) for i,ip in enumerate(sorted(ips))}

def network(frame,identity,all_ips,reference=1000,max_nodes=50):
    volume=frame.groupby('source').packets.sum().add(frame.groupby('destination').packets.sum(),fill_value=0) if not frame.empty else pd.Series(dtype=float)
    # Stable full-study layout. Only the busiest nodes are drawn; inspector includes every IP.
    ips=sorted(all_ips);pos=positions(ips);shown=set(volume.nlargest(max_nodes).index) if len(ips)>max_nodes else set(ips)
    fig=go.Figure()
    if not frame.empty:
        edges=frame.groupby(['source','destination']).packets.sum().nlargest(60)
        x=[];y=[]
        for (a,b),count in edges.items():
            if a in shown and b in shown:x += [pos[a][0],pos[b][0],None];y += [pos[a][1],pos[b][1],None]
        fig.add_trace(go.Scatter(x=x,y=y,mode='lines',line=dict(color='rgba(110,140,170,.22)',width=1),hoverinfo='skip',showlegend=False))
    for ip in ips:
        if ip not in shown:continue
        x,y=pos[ip];n=int(volume.get(ip,0));opacity=.08+.92*min(1,n/max(1,reference))
        own=identity[(identity.ip==ip)&(identity.association=='Ethernet source association')] if not identity.empty else identity
        hw=own.sort_values('packets',ascending=False).iloc[0].hardware if not own.empty else 'Unresolved'
        symbol='◆' if 'Raspberry' in hw else '■' if 'Espressif' in hw else '⬟' if 'gateway' in hw.lower() else '●'
        relevant=frame[(frame.source==ip)|(frame.destination==ip)]
        cats=sorted(set(relevant.category)-{'Normal','Unclassified'})
        icons=''.join(ICONS.get(c,'❔') for c in cats)
        hover=f'{ip}<br>{n:,} endpoint packet appearances<br>{hw}<br>'+', '.join(cats)
        fig.add_trace(go.Scatter(x=[x],y=[y],mode='markers+text',text=[symbol+' '+ip.split('.')[-1]+(' '+icons if n else '')],textposition='top center',textfont=dict(size=11,color='rgba(230,240,255,.85)'),marker=dict(size=18+min(24,math.sqrt(n)/3),color=f'rgba(255,255,255,{opacity})',line=dict(color='#ef786f' if cats else '#75a6bd',width=2)),customdata=[[ip]],hovertext=[hover],hoverinfo='text',showlegend=False))
    fig.update_layout(height=430,margin=dict(l=15,r=15,t=15,b=15),paper_bgcolor='#0e1624',plot_bgcolor='#0e1624',xaxis=dict(visible=False,range=[-1.35,1.35]),yaxis=dict(visible=False,range=[-1.35,1.35],scaleanchor='x'),clickmode='event+select')
    return fig

def timeline(summary,clock,start,end):
    fig=go.Figure()
    for cat,g in summary.groupby('category'):
        # Bins without observations are missing coverage, not confirmed zero intensity.
        g=g.sort_values('t');x=[];y=[];previous=None
        for row in g.itertuples():
            if previous is not None and row.t-previous>60:x.append(None);y.append(None)
            x.append(pd.to_datetime(row.t,unit='s',utc=True));y.append(row.packets/60);previous=row.t
        fig.add_trace(go.Scatter(x=x,y=y,name=ICONS.get(cat,'❔')+' '+cat,mode='lines+markers',marker=dict(size=3)))
    fig.add_vrect(x0=pd.to_datetime(start,unit='s',utc=True),x1=pd.to_datetime(end,unit='s',utc=True),fillcolor='white',opacity=.15,line_width=0)
    fig.update_layout(height=310,margin=dict(l=15,r=15,t=90,b=65),yaxis_title='Observed packets/s (60 s bins)',template='plotly_dark',legend=dict(orientation='h',yanchor='bottom',y=1.06,xanchor='left',x=0,font=dict(size=10),entrywidth=140))
    fig.update_xaxes(tickformat='%d %b %Y<br>%H:%M UTC',hoverformat='%d %b %Y %H:%M:%S UTC')
    return fig

def gif(summary,ips,max_frames=90):
    from PIL import Image,ImageDraw
    frames=[];times=sorted(summary.t.unique());stride=max(1,math.ceil(len(times)/max_frames))
    peak=max(1,summary.packets.max())
    for t in times[::stride]:
        im=Image.new('RGB',(800,420),'#0e1624');d=ImageDraw.Draw(im)
        d.text((20,15),str(pd.to_datetime(t,unit='s',utc=True)),fill='white')
        d.text((20,42),'Observed packet counts per minute; gaps skipped. Folder labels, not verified attacks.',fill='#aabbcc')
        for i,row in enumerate(summary[summary.t==t].itertuples()):
            y=85+i*33;d.text((20,y),row.category,fill='white');w=int(500*row.packets/peak);d.rectangle((200,y,200+w,y+20),fill='#85bdde');d.text((710,y),str(row.packets),fill='white')
        frames.append(im)
    if not frames:return b''
    out=io.BytesIO();frames[0].save(out,format='GIF',save_all=True,append_images=frames[1:],duration=500,loop=0);return out.getvalue()
