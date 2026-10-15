"""Offline canvas force layout with collision avoidance, drag and hover."""
import json
from pathlib import Path
import streamlit.components.v1 as components

_component=components.declare_component("farmflow_network",path=str(Path(__file__).parent/"network_component"))

def floating_network(frame,identity,ips,reference):
    return _component(html=floating_html(frame,identity,ips,reference),key="floating_network",default=None)

from visuals import network

def floating_html(frame,identity,ips,reference):
    fig=network(frame,identity,ips,reference)
    nodes=[]
    for trace in fig.data:
        if trace.customdata is None:continue
        nodes.append(dict(id=trace.customdata[0][0],label=trace.text[0],color=trace.marker.color,border=trace.marker.line.color,r=float(trace.marker.size)/2,tip=trace.hovertext[0].replace('<br>','\n')))
    kept={n['id'] for n in nodes}
    edges=[dict(a=a,b=b) for (a,b),n in frame.groupby(['source','destination']).packets.sum().nlargest(80).items() if a in kept and b in kept and a!=b]
    payload=json.dumps(dict(nodes=nodes,edges=edges)).replace('<','\\u003c')
    return '''<!doctype html><meta charset="utf-8"><style>body{margin:0;background:#0e1624;color:#edf3fb;font:12px sans-serif}canvas{width:100%;height:420px;touch-action:none}#tip{position:absolute;pointer-events:none;background:#172233;padding:9px;border-radius:6px;white-space:pre-line;display:none;max-width:280px}button{background:#172233;color:#edf3fb;border:1px solid #64748b;border-radius:5px;padding:5px;cursor:pointer}</style><button id="pause">Pause motion</button> <span>Click to inspect · drag to arrange · hover for evidence</span><canvas id="view"></canvas><div id="tip"></div><script>
const data=PAYLOAD,canvas=document.getElementById('view'),ctx=canvas.getContext('2d'),tip=document.getElementById('tip');let w=800,h=420,drag=null,running=true,down=null,moved=false,selected=null;
const cacheKey='farmflow-floats-'+data.nodes.map(n=>n.id).sort().join('|');let cache={};try{cache=JSON.parse(sessionStorage.getItem(cacheKey)||'{}')}catch(e){}
const nodes=data.nodes.map((n,i)=>({...n,x:cache[n.id]?.x||400+150*Math.cos(i*2*Math.PI/data.nodes.length),y:cache[n.id]?.y||210+140*Math.sin(i*2*Math.PI/data.nodes.length),vx:0,vy:0})),byId=Object.fromEntries(nodes.map(n=>[n.id,n]));
function resize(){const old=w;w=canvas.clientWidth;canvas.width=w*devicePixelRatio;canvas.height=h*devicePixelRatio;ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);nodes.forEach(n=>n.x=Math.max(55,Math.min(w-55,n.x*w/old)))}new ResizeObserver(resize).observe(canvas);
document.getElementById('pause').onclick=()=>{running=!running;document.getElementById('pause').textContent=running?'Pause motion':'Resume motion'};
function point(e){let r=canvas.getBoundingClientRect();return{x:e.clientX-r.left,y:e.clientY-r.top}}function hit(p){return nodes.find(n=>Math.hypot(n.x-p.x,n.y-p.y)<n.r+10)}
canvas.onpointerdown=e=>{down=point(e);moved=false;drag=hit(down);if(drag)canvas.setPointerCapture(e.pointerId)};canvas.onpointerup=e=>{if(drag&&!moved){selected=drag.id;window.parent.postMessage({type:'farmflow:select',ip:drag.id},'*')}drag=null;down=null};canvas.onpointercancel=()=>{drag=null;down=null};
canvas.onpointermove=e=>{let p=point(e);if(down&&Math.hypot(p.x-down.x,p.y-down.y)>6)moved=true;if(drag&&moved){drag.x=p.x;drag.y=p.y;drag.vx=drag.vy=0}let n=hit(p);tip.style.display=n?'block':'none';if(n){tip.textContent=n.tip;tip.style.left=Math.min(p.x+12,w-290)+'px';tip.style.top=Math.max(30,p.y-20)+'px'}};canvas.onpointerleave=()=>tip.style.display='none';
let ticks=0;function draw(){if(running){for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){let a=nodes[i],b=nodes[j],dx=a.x-b.x,dy=a.y-b.y,d=Math.max(1,Math.hypot(dx,dy)),space=a.r+b.r+65,f=1300/(d*d)+(d<space?(space-d)*.07:0);a.vx+=dx/d*f;a.vy+=dy/d*f;b.vx-=dx/d*f;b.vy-=dy/d*f}for(let e of data.edges){let a=byId[e.a],b=byId[e.b],dx=b.x-a.x,dy=b.y-a.y,d=Math.max(1,Math.hypot(dx,dy)),f=(d-135)*.0015;a.vx+=dx/d*f;a.vy+=dy/d*f;b.vx-=dx/d*f;b.vy-=dy/d*f}for(let n of nodes){if(n===drag)continue;n.vx=(n.vx+(w/2-n.x)*.0008)*.82;n.vy=(n.vy+(h/2-n.y)*.0008)*.82;n.x=Math.max(n.r+35,Math.min(w-n.r-35,n.x+n.vx));n.y=Math.max(n.r+28,Math.min(h-n.r-18,n.y+n.vy))}}
ctx.clearRect(0,0,w,h);ctx.strokeStyle='rgba(110,140,170,.25)';for(let e of data.edges){ctx.beginPath();ctx.moveTo(byId[e.a].x,byId[e.a].y);ctx.lineTo(byId[e.b].x,byId[e.b].y);ctx.stroke()}for(let n of nodes){ctx.beginPath();ctx.arc(n.x,n.y,n.r,0,Math.PI*2);ctx.fillStyle=n.color;ctx.fill();ctx.strokeStyle=n.id===selected?'#6ee7b7':n.border;ctx.lineWidth=n.id===selected?4:2;ctx.stroke();ctx.fillStyle='#edf3fb';ctx.textAlign='center';ctx.font='11px sans-serif';ctx.fillText(n.label,n.x,n.y-n.r-8)}if(++ticks%15===0)try{sessionStorage.setItem(cacheKey,JSON.stringify(Object.fromEntries(nodes.map(n=>[n.id,{x:n.x,y:n.y}]))))}catch(e){}requestAnimationFrame(draw)}resize();draw();</script>'''.replace('PAYLOAD',payload)
