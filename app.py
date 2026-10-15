"""FarmFlow Studio — run with streamlit run app.py"""
import os,json,hashlib,sqlite3
from pathlib import Path
from datetime import datetime,timezone,timedelta
import pandas as pd
import streamlit as st
from indexer import build,manifest,read,selected,identities
from capture_filters import capture_tags
from timeline_engine import ICONS,episode_proxies
from visuals import network,timeline,gif
from floating import floating_network
from navigation import event_rail,event_starts
import streamlit.components.v1 as components
from data import Table
from companion import run_turn
from presentation import figure,bundle
from display_time import readable_frame
import media

st.set_page_config(page_title='FarmFlow · Temporal Studio',layout='wide')
st.markdown("""<style>
.st-key-build_index button {background:#238636!important;border-color:#2ea043!important;color:white!important}
.st-key-build_index button:hover {background:#2ea043!important}
.st-key-build_index button:disabled {opacity:.45}
.st-key-timeline_dock {position:sticky;top:2.9rem;z-index:90;background:#0e1624;border-bottom:1px solid #334155;padding:6px 10px;border-radius:8px}
.st-key-timeline_dock [data-testid="stVerticalBlock"] {gap:.2rem}
</style>""",unsafe_allow_html=True)
st.title('FarmFlow · Temporal Studio')
st.caption('Sense → Data · Structure → Information · Mental Model → Knowledge · Share → Expertise')
DEFAULT=r'D:\dev\uWorkspace\KiriProjects\Kiri03\github\WFServer01\IoTSensors\ProjFarmFlow\farm-flow\Captures'
with st.sidebar:
    st.header('Research captures')
    root=st.text_input('Captures directory',value=DEFAULT)
    zone=st.text_input('Filename timezone (IANA)',value='UTC',help='Packet timestamps are absolute. Filename time needs its own timezone assumption.')
    paths=sorted(p for p in Path(root).rglob('*') if p.is_file() and p.suffix.lower() in ('.pcap','.pcapng','.cap')) if Path(root).is_dir() else []
    st.caption(f'{len(paths):,} capture files found recursively')
    categories=sorted({capture_tags(p)[1] for p in paths})
    include=st.multiselect('Include categories',categories,default=categories)
    exclude=st.multiselect('Exclude categories',categories)
    chosen=[p for p in paths if capture_tags(p)[1] in include and capture_tags(p)[1] not in exclude]
    dbpath=Path('studies')/'farmflow.sqlite'
    if st.button('Build / rebuild study index',disabled=not chosen,type='primary',key='build_index'):
        bar=st.progress(0,text='Reading captures')
        try:
            build(chosen,dbpath,zone,lambda p,t:bar.progress(min(p,1.0),text=t));bar.progress(1.0,text='Index ready')
            st.session_state.pop('cursor',None);st.session_state.pop('time_slider_time',None);st.session_state.pop('time_slider_filename_clock',None);st.session_state['playing']=False
            st.success('Study built from your captures. No example data loaded.')
        except Exception as exc:st.error(f'Index failed: {type(exc).__name__}: {exc}')
    with st.expander('Companion connection'):
        key=st.text_input('OpenAI API key',value=os.getenv('OPENAI_API_KEY',''),type='password')
        model=st.text_input('Chat model',value='gpt-4.1')
        image_model=st.text_input('Image model',value='gpt-image-1')
        audio_model=st.text_input('Speech model',value='gpt-4o-mini-tts')
        video_model=st.text_input('Video model',value='sora-2')
        st.caption('Model availability depends on your API project. Calls occur only when you send a prompt or press a media button. Selected table schemas, samples and bounded computed results are sent to OpenAI; raw PCAPs stay local.')
if not dbpath.exists():
    st.info('Choose the real Captures directory, then build the study index. CSV files and example directories are not required.');st.stop()
meta=read(dbpath,'SELECT * FROM meta').set_index('key').value.to_dict()
if chosen and manifest(chosen,zone)!=meta.get('manifest'):st.warning('The folder selection or files differ from the indexed study. Rebuild to apply the new selection. The current display uses the saved index.')
captures=read(dbpath,'SELECT * FROM captures')
indexed_categories=sorted(captures.category.unique())
with st.sidebar:
    active=st.multiselect('Display indexed categories',indexed_categories,default=indexed_categories)
    clock_label=st.radio('Timeline clock',['Packet timestamps','Filename-aligned (assumption)'])
    clock='time' if clock_label=='Packet timestamps' else 'filename_clock'
    window=st.select_slider('Window duration (seconds)',options=[5,15,30,60,300,900,3600],value=60)
    speed=st.select_slider('Advance per playback tick (seconds)',options=[5,15,30,60,300,900,3600],value=60)
    skip=st.checkbox('Skip unobserved gaps during playback',value=False)
    reference=st.number_input('Fully white at endpoint packets/window',min_value=1,value=1000)
    st.caption('Whiteness uses this fixed scale across time. Transparent = fewer observed packets, not a trusted or safe device.')
    if st.button('Pause' if st.session_state.get('playing') else 'Play'):
        st.session_state['playing']=not st.session_state.get('playing',False)
    st.caption('Build studio-3 · Time labels: UTC · 5-second indexing bins')
allips=read(dbpath,'SELECT source AS ip FROM observations UNION SELECT destination AS ip FROM observations').ip.tolist()
summary=read(dbpath,f'SELECT CAST({clock}/60 AS INTEGER)*60 AS t, category,SUM(packets) AS packets FROM observations GROUP BY t,category')
summary=summary[summary.category.isin(active)]
if summary.empty:st.info('No indexed observations in the selected categories.');st.stop()
bounds=read(dbpath,f'SELECT MIN({clock}) AS first,MAX({clock}) AS last FROM observations').iloc[0]
lo=int(bounds['first']);hi=max(lo+5,int(bounds['last'])+5)
with st.sidebar.expander('Jump to a date and time'):
    jump_day=st.date_input('UTC date',value=datetime.fromtimestamp(lo,timezone.utc).date(),min_value=datetime.fromtimestamp(lo,timezone.utc).date(),max_value=datetime.fromtimestamp(hi,timezone.utc).date())
    jump_time=st.time_input('UTC time',value=datetime.fromtimestamp(lo,timezone.utc).time().replace(tzinfo=None),step=timedelta(seconds=5))
    if st.button('Jump'):
        target=int(datetime.combine(jump_day,jump_time,tzinfo=timezone.utc).timestamp())
        target=max(lo,min(hi-5,(target//5)*5));st.session_state['cursor']=target
        st.session_state['time_slider_'+clock]=datetime.fromtimestamp(target,timezone.utc)
        st.session_state['playing']=False


def stamp(t):return datetime.fromtimestamp(t,timezone.utc).strftime('%d %b %Y, %H:%M:%S UTC')

def dfshow(frame):st.dataframe(readable_frame(frame),hide_index=True,width='stretch')

@st.fragment(run_every=1 if st.session_state.get('playing') else None)
def workspace():
    cursor=st.session_state.get('cursor',lo)
    if st.session_state.get('playing'):
        cursor=min(hi-5,cursor+speed)
        if skip:
            available=summary[summary.t+60>cursor]
            if not available.empty and not ((summary.t<=cursor)&(summary.t+60>cursor)).any():cursor=int(available.t.min())
        if cursor>=hi-5:st.session_state['playing']=False
    cursor=max(lo,min(hi-5,cursor))
    def seek(target):
        target=max(lo,min(hi-5,int(target)//5*5))
        st.session_state['cursor']=target
        st.session_state['time_slider_'+clock]=datetime.fromtimestamp(target,timezone.utc)
        st.session_state['playing']=False
    def marker_selected():
        points=st.session_state.get('event_rail',{}).get('selection',{}).get('points',[])
        if points and points[0].get('customdata'):seek(points[0]['customdata'][0])
    def adjacent(direction):
        current=st.session_state.get('cursor',lo)
        times=sorted({max(lo,t) for t,c in event_starts(summary)})
        candidates=[t for t in times if t>current] if direction>0 else [t for t in times if t<current]
        if candidates:seek(min(candidates) if direction>0 else max(candidates))
    if not st.session_state.get('playing'):
        cursor=int(st.session_state.get('time_slider_'+clock,datetime.fromtimestamp(cursor,timezone.utc)).timestamp())
    with st.container(key='timeline_dock'):
        st.plotly_chart(event_rail(summary,cursor,cursor+window,lo,hi),width='stretch',key='event_rail',on_select=marker_selected,selection_mode='points',config={'displayModeBar':False,'scrollZoom':False})
        if st.session_state.get('playing'):st.session_state['time_slider_'+clock]=datetime.fromtimestamp(cursor,timezone.utc)
        startdt=st.slider('Observation time · UTC',min_value=datetime.fromtimestamp(lo,timezone.utc),max_value=datetime.fromtimestamp(hi-5,timezone.utc),step=timedelta(seconds=5),format='DD MMM YYYY HH:mm:ss',key='time_slider_'+clock) if hi-lo>5 else datetime.fromtimestamp(lo,timezone.utc)
        start=cursor if st.session_state.get('playing') else int(startdt.timestamp())
        st.session_state['cursor']=start;end=min(start+window,hi)
        prev,following,description=st.columns([1,1,4])
        prev.button('← Previous event',on_click=adjacent,args=(-1,))
        following.button('Next event →',on_click=adjacent,args=(1,))
        description.caption('Click a tick to jump · coral = attack-folder activity · blue = other activity · nearby starts clustered')
        st.caption(f'{stamp(start)} → {stamp(end)} · {clock_label}')
    frame=selected(dbpath,start,end,active,clock)
    ident=identities(frame)
    episode_bins=frame.groupby(['category','source','destination',clock],as_index=False).packets.sum()
    if clock!='time':episode_bins=episode_bins.rename(columns={clock:'time'})
    episodes=episode_proxies(episode_bins,30) if not episode_bins.empty else pd.DataFrame(columns=['source','destination'])
    scope_id=hashlib.sha256(json.dumps([meta.get('manifest'),clock,start,end,active]).encode()).hexdigest()
    notes=['Exact same-time/same-bytes packets deduplicated across captures, assuming one observation point. First file supplies category when duplicate labels conflict; conflicts are recorded in capture provenance.','Folder categories are provenance, not independently detected attacks. MAC associations do not establish ownership. Scores are heuristic evidence scores, not calibrated probabilities.','Counts use 5-second bins. MQTT decoding is packet-local without TCP reassembly; encrypted/fragmented payloads can remain unresolved. Gaps mean unknown coverage.']
    tables=[Table('activity','Window packet observations','Indexed captures',scope_id,frame,notes),Table('identities','Window IP/MAC associations','Indexed captures',scope_id,ident,notes),Table('study_intensity','Whole study observed minute intensity','Indexed captures',meta.get('manifest',''),summary.rename(columns={'t':'time'}),notes+['Whole indexed date range, selected display categories; packets are counts per observed minute bin. Missing minute bins are unknown coverage.']),Table('provenance','Whole study capture provenance','Indexed captures',meta.get('manifest',''),captures,notes+['All indexed captures, including categories hidden from the display. Do not sum overlapping time durations.'])]
    context={'start':stamp(start),'end':stamp(end),'clock':clock_label,'categories':active,'scope_sha256':scope_id,'notes':notes}
    if st.session_state.get('scope_id')!=scope_id:
        st.session_state.update(scope_id=scope_id,history=[],results=[])
    count=int(frame.packets.sum()) if not frame.empty else 0
    c1,c2,c3=st.columns(3)
    c1.metric('Observed packets',f'{count:,}')
    c2.metric('Active IPs',len(set(frame.source)|set(frame.destination)))
    c3.metric('Folder-labelled attack packets',f'{int(frame.loc[~frame.category.isin(["Normal","Unclassified"]),"packets"].sum()):,}')
    sense,structure,mental,share=st.tabs(['◉ Sense · Data','⌘ Structure · Information','◇ Mental Model · Knowledge','↗ Share · Expertise'])
    with sense:
        left,right=st.columns([2.2,1])
        with left:
            node_click=floating_network(frame,ident,allips,reference)
            st.caption('White opacity = activity · ◆ Pi candidate · ■ Espressif candidate · red outline + icon = attack-folder appearance. Nodes float to find space; drag to rearrange or pause motion. Lines show communication pairs; click a node to update the inspector; dragging only rearranges it. At most 50 active/busiest IPs drawn.')
        with right:
            if node_click and node_click.get('ip') in allips and node_click.get('token')!=st.session_state.get('last_node_click'):
                st.session_state['inspect_ip']=node_click['ip']
                st.session_state['last_node_click']=node_click['token']
            if st.session_state.get('inspect_ip') not in allips:st.session_state['inspect_ip']=allips[0]
            ip=st.selectbox('Inspect IP',allips,key='inspect_ip')
            own=ident[ident.ip==ip] if not ident.empty else ident
            if own.empty:st.caption('No MAC association observed in this window.')
            else:
                best=own.sort_values(['hardware_score','packets'],ascending=False).iloc[0]
                st.write(best.hardware);st.caption(f'Hardware evidence score {best.hardware_score}% · {best.association}')
                for row in own.itertuples():st.code(f'{row.mac}\n{row.association}',language=None)
            local=frame[(frame.source==ip)|(frame.destination==ip)]
            if st.checkbox('Include this IP history in companion context',value=False,help='Loads this IP across the complete indexed date range, including categories hidden from the current display.'):
                history_frame=read(dbpath,'SELECT time,filename_clock,category,source,destination,source_mac,destination_mac,protocol,activity,topic,purpose,purpose_score,SUM(packets) AS packets FROM observations WHERE source=? OR destination=? GROUP BY time,filename_clock,category,source,destination,source_mac,destination_mac,protocol,activity,topic,purpose,purpose_score',(ip,ip))
                tables.append(Table('ip_history','Whole-study history for '+ip,'Indexed captures',meta.get('manifest',''),history_frame,notes+['Entire study packet-time history for selected IP, including hidden categories; MAC ownership still unverified.']))
                st.caption(f'{len(history_frame):,} time-binned observations available to companion.')
            for cat,g in local.groupby('category'):st.write(f'{ICONS.get(cat,"❔")} {cat}: {int(g.packets.sum()):,} packets involving this IP')
            if not local.empty:
                incident_count=len(episodes[(episodes.source==ip)|(episodes.destination==ip)])
                st.caption(f'{incident_count:,} window-local attack episode proxies involving this IP (not confirmed incidents).')
                st.caption('Activities');st.write(', '.join(local.activity.unique()[:8]))
                topics=local[local.topic!=''].topic.unique()
                if len(topics):st.caption('Observed topic candidates');st.write(', '.join(topics[:8]))
                st.caption(f'Outbound {int(local.loc[local.source==ip,"packets"].sum()):,} · inbound {int(local.loc[local.destination==ip,"packets"].sum()):,}; self-addressed packets can appear in both.')
            with st.expander('Evidence and scores'):dfshow(own)
        st.plotly_chart(timeline(summary,clock,start,end),width='stretch')
        if frame.empty:st.info('No packets observed in this window. This does not establish attack-free coverage.')
        with st.expander('Observations, provenance and limitations'):
            dfshow(frame);dfshow(captures)
            for note in notes:st.write(note)
            st.caption('Filename start versus packet start is available in provenance. Filename-aligned time shifts each file relative to its first packet; use packet time for cross-file chronology unless that assumption is validated.')
    chat_scope=hashlib.sha256((scope_id+str([(t.id,t.name) for t in tables])).encode()).hexdigest()
    if st.session_state.get('chat_scope')!=chat_scope:
        st.session_state.update(chat_scope=chat_scope,history=[],results=[])
    with structure:
        st.caption('Computed relationships are separate from observations. Use the companion below to request graphs, comparisons, mathematical models, or a narrative tied to this window.')
        if not frame.empty:
            a,b=st.columns(2)
            with a:st.bar_chart(frame.groupby('activity').packets.sum(),horizontal=True)
            with b:st.bar_chart(frame.groupby('category').packets.sum(),horizontal=True)
            ep=frame.rename(columns={clock:'selected_time'}) if clock!='time' else frame.assign(selected_time=frame.time)
            ep=ep.rename(columns={'selected_time':'event_time'})
            bins=ep.groupby(['category','source','destination','event_time'],as_index=False).packets.sum().rename(columns={'event_time':'time'})
            bins=bins[~bins.category.isin(['Normal','Unclassified'])]
            if not bins.empty:
                episodes=episode_proxies(bins,30)
                st.caption(f'{len(episodes):,} window-local episode proxies (30-second maximum gap). Window boundaries truncate episodes; these are not confirmed incidents.');dfshow(episodes)
    with mental:
        st.markdown('A device estimate is a hypothesis with evidence and alternatives. An IP change, a MAC change, and a compromise are separate events.')
        st.latex(r'I_t(ip)=\{(mac,\ evidence,\ score)\mid observations\ in\ [t,t+\Delta)\}')
        st.caption('The score describes support for a designation. It is not P(compromise), and current scores have not been calibrated against labelled hardware ground truth.')
        hypothesis=st.text_area('Candidate mental model',key='hypothesis')
        falsifier=st.text_area('What observation would reject it?',key='falsifier')
        st.write('Next tests: compare MAC source associations in adjacent windows; inspect ARP claims and DHCP leases; corroborate topic meaning with device code or deployment records. Heat/moisture topics alone do not prove an irrigation action.')
    with share:
        action=st.text_area('External application / next action',placeholder='Who will use this finding, what will they do, and how will the result be checked?',key='action')
        session={'title':'FarmFlow temporal study','scope':context,'history':st.session_state.history,'results':st.session_state.results,'next_action':action,'eunits':[{'hypothesis':st.session_state.get('hypothesis',''),'reject_if':st.session_state.get('falsifier','')}]}
        st.download_button('Download research session',bundle(session),'farmflow_session.zip','application/zip')
        st.download_button('Window observations CSV',readable_frame(frame).to_csv(index=False),'window_observations.csv','text/csv')
        if st.button('Create observed-intensity animation (local)'):st.session_state['gif']=gif(summary,allips)
        if st.session_state.get('gif'):st.image(st.session_state['gif']);st.download_button('Download GIF',st.session_state['gif'],'observed_intensity.gif','image/gif')
        st.caption('Media below are generated illustrations or AI narration. They are not measurement evidence. API generation may incur charges.')
        media_prompt=st.text_area('Media text / prompt',value='',key='media_prompt',help='Paste a reviewed companion explanation. It will be sent to OpenAI when a generation button is pressed.')
        m1,m2,m3=st.columns(3)
        try:
            if m1.button('Generate illustration',disabled=not(key and media_prompt)):
                st.session_state['illustration']=media.image(key,media_prompt,image_model)
            if m2.button('Generate AI narration',disabled=not(key and media_prompt)):
                st.session_state['narration']=media.speech(key,media_prompt,audio_model)
            if m3.button('Start conceptual video',disabled=not(key and media_prompt)):
                st.session_state['video_job']=media.start_video(key,media_prompt,video_model)
            if st.session_state.get('illustration'):
                st.image(st.session_state['illustration'],caption='AI-generated conceptual illustration');st.download_button('Save image',st.session_state['illustration'],'illustration.png','image/png')
            if st.session_state.get('narration'):
                st.caption('AI-generated voice');st.audio(st.session_state['narration']);st.download_button('Save audio',st.session_state['narration'],'narration.mp3','audio/mpeg')
            job=st.session_state.get('video_job')
            if job:
                st.write(f'Video: {job["status"]} · {job["id"]}')
                if st.button('Check video job'):
                    job,video=media.poll_video(key,job['id']);st.session_state['video_job']=job
                    if video:st.session_state['video']=video
                    st.write(job['status'])
                    if job.get('error'):st.write(job['error'])
            if st.session_state.get('video'):st.video(st.session_state['video']);st.download_button('Save video',st.session_state['video'],'conceptual_video.mp4','video/mp4')
        except Exception as exc:st.error(media.error_text(exc))
    st.divider()
    st.subheader('Companion · current temporal window')
    st.caption('Pause playback to investigate. Moving the window starts a new conversation scope; download the current session before moving. Graphs and equations appear with the answer. No cloud calls occur during playback.')
    for msg in st.session_state.history:
        with st.chat_message(msg['role']):st.markdown(msg['content'])
    st.caption('The companion can also query the whole-study minute-intensity table and capture provenance; those tables are explicitly distinguished from the current window.')
    question=st.text_input('Ask about this window',placeholder='Compare the active MACs, plot activity, and propose a falsifiable explanation.',key='question')
    if st.button('Ask companion',disabled=not(key and question) or st.session_state.get('playing',False)):
        try:
            with st.spinner('Computing from the selected observations…'):
                answer,results,usage=run_turn(tables,question,st.session_state.history,{},key,model,st.session_state.results)
            st.session_state.history += [{'role':'user','content':question},{'role':'assistant','content':answer}];st.session_state.results += results
            st.markdown(answer)
        except Exception as exc:st.error(media.error_text(exc))
    for result in st.session_state.results:
        fig=figure(result)
        if fig is not None:st.plotly_chart(fig,width='stretch')
        if result.get('formula'):st.latex(result['formula'])
        with st.expander(f'{result["id"]} · computation evidence'):st.json(result)
workspace()
