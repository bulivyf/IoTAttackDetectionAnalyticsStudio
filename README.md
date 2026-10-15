# FarmFlow Temporal Studio

A local Streamlit research application for real PCAP/PCAPNG captures. No sample directory, CSV export or TShark installation is required. Python 3.11+ recommended.

## Windows start

Extract this ZIP to a new project directory. Open PowerShell in `farmflow_studio`:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Alternatively run `launch.ps1`. Set `OPENAI_API_KEY` before launching (restart the shell after changing Windows environment variables), or enter it in the sidebar. The variable is OPENAI_API_KEY, not OPEN_API_KEY. Local analysis needs no API key.

Point the sidebar at your `farm-flow\Captures` folder. Subdirectories, including month and attack categories, are searched recursively. Select include/exclude categories and build the index. Indexing is streaming and can take time on large datasets; status shows the current capture and packet count. Keep the browser session open during indexing. Indexes are saved locally under `studies`. Rebuild when files or folder selection changes; the app warns if its manifest differs. This version rebuilds the selected study, rather than incrementally appending to it.

This code relies on the Farm Flow data, which is best downloaded via this link: https://zenodo.org/records/10964648.

The related article is here: https://www.sciencedirect.com/science/article/pii/S0045790624008188


## Time and perception

- **Sense → Data:** datetime slider, stable schematic IP map, observed MAC associations, packet activity and provenance. All visible dates are UTC calendar dates. Packet timestamps are default; filename-aligned time is a separately labelled assumption. The filename timezone is editable. There is no assumption that all data covers exactly three consecutive days: the slider spans whatever dates the actual captures contain.
- **Structure → Information:** category/activity intensity, window-local episode proxies and companion-generated graphs. White opacity shows endpoint packet appearances against a fixed adjustable reference, so successive windows are comparable. Red borders/icons mean attack-folder appearance, not proof of compromise. Connections are undirected schematic pairs; source/destination counts are available in the inspector. Layout is not a physical topology.
- **Mental Model → Knowledge:** explicit candidate explanation, rejection criterion, evidence limits and mathematical expressions. A score is a transparent heuristic evidence score, not a calibrated probability. Keep hypotheses revisable.
- **Share → Expertise:** record the external application/next action; download notes, data, models and interactive graphs. This operationalizes the E-theory mapping supplied in this conversation; it is not a claim to implement a separately verified full theory specification.

Use Play/Pause and advance-per-tick to fast/slow forward. Unobserved intervals remain visible; optional skip-gaps changes playback only. Pause to ask the companion. Changing the time window starts a new chat scope; save the current research session first. The companion receives current-window observations and identities, whole-study minute intensity and full capture provenance as distinct tables. Optionally include the inspected IP’s complete indexed history using its checkbox. History/provenance include hidden display categories and are labelled accordingly; apply explicit filters when comparing them. Raw packet bytes are never sent. Whole-study intensity is calculated locally. Five-second bins limit event-time precision; window boundaries use these bins.

Select a node in the map or use the IP inspector. At most 50 busiest nodes are drawn when needed; every IP remains in the inspector. The map uses last-octet labels for compactness; hover/inspector give full addresses, including IPv6.

## Identity and scientific limits

Source Ethernet association, destination next-hop association and ARP claimed identities are separately labelled. A remote public IP's true MAC/hardware cannot be identified from a local Ethernet next hop. OUI family estimates are candidate interface families, not proof of exact board. MAC spoofing and virtual interfaces are possible. The included MAC-bound working role priors come from this research conversation; role scores are capped at 75 and must be validated against deployment/code. An IP alone never transfers those roles to a different MAC.

MQTT topic text can support a temperature/moisture/light/alarm messaging purpose at a 70% heuristic score. This identifies message semantics, not the attached physical sensor or a causal actuator command. Unresolved/encrypted traffic is shown honestly. Native decoding is packet-local: no TCP reassembly, full MQTT session reconstruction, DHCP lease decoder, DNS answer resolver, IPv6 extension parsing or full application protocol decoder is included. Payload text is bounded and untrusted. Use Wireshark/TShark for packet-level verification.

Exact duplicate detection spans all selected files using an on-disk fingerprint of exact timestamp, interface scope, link type, wire length and captured bytes. Different-time retransmissions are retained. This assumes selected captures share one observation point; analyze independent vantage points as separate studies. When duplicate packet labels conflict, the first path in sorted order supplies the retained category; provenance reports the conflict count. It does not adjudicate label truth. Full capture SHA-256 hashes and packet counts are exported in provenance. A failed build leaves the previous complete index intact.

Incident counts are **window-local episode proxies** grouped by category and IP pair, with a 30-second tolerated gap plus bin resolution. They are truncated at the current window boundaries. They are not independent confirmed attacks. Traffic intensity counts packets, not incidents, and an endpoint's activity includes both sender and receiver appearances. Capture gaps mean missing/unknown coverage, not zero attacks. Daily/device comparisons require a compatible sampling denominator.

## OpenAI companion and media

The Responses API companion can request bounded local computations: summaries, group/time series, graphs, correlation, linear/rate models and robust anomaly candidates. It cannot execute arbitrary generated Python, shell or SQL. Results have source hashes and query IDs; numeric claims require computation. Cloud calls send table schemas, small samples and bounded result rows, not raw PCAPs. IPs/MACs/topic names may be included. Keys are not written into exports or files. The local server should remain bound to localhost; do not expose it without authentication.

Text, stories, LaTeX equations and interactive measured graphs are supported in chat. Share also offers a local observed-intensity GIF and explicit API buttons for conceptual image generation, AI speech, and asynchronous conceptual video. Paste a reviewed explanation/prompt into the media field; generation is deliberate, not triggered by slider movement. Generated images/videos are illustrations, never forensic evidence. Video completion is checked with a button; there is no blocking polling loop. Download completed media promptly. Model IDs are editable because access and availability vary. Image/video/audio generation can incur API charges independently of chat. A ChatGPT subscription is separate from API billing.

Generated media stays in the current browser session until downloaded. Chat session ZIPs contain text, computed results and graphs, but do not embed generated image/audio/video; download those separately. There is no microphone/transcription or arbitrary media editing in this version.

If an API call fails, the app reports its safe HTTP/code fields. `insufficient_quota` points to API project billing/quota; `rate_limit_exceeded` means request/token throughput limits; `model_not_found` requires checking the configured model/project access. Keys and raw request bodies are never printed.

API references used: https://developers.openai.com/api/docs/guides/function-calling , https://developers.openai.com/api/docs/guides/image-generation , https://developers.openai.com/api/docs/guides/text-to-speech , https://developers.openai.com/api/docs/guides/video-generation . Availability can change; configure supported models in your project.

## Verification

Run `python -m unittest discover -v`. Tests use tiny generated packets only inside temporary test folders; the application never loads them. The supplied normal merged research capture was also used for a real-data indexing/deduplication check. Your full Windows directory is not accessible from this environment, so its complete corpus must be indexed locally. API calls are tested with mocks; live paid generation was not performed.

## Studio 2 display update

The index action has its own green button; selected tags retain the existing theme color. The offline canvas network uses repulsion, link attraction, collision spacing and viewport bounds. Drag nodes, hover for details, or pause motion; use the IP selector for the full inspector. Positions are remembered within the browser session when the same node set is displayed. This is a schematic layout, not inferred geography.

A compact timeline dock stays at the top as you scroll. Its tick rail marks activity starts: the first observed minute of a category, or renewed activity after a gap greater than one minute. Coral ticks include attack-folder categories; blue ticks represent other activity. Nearby starts are grouped into at most about 100 ticks, with hover details. Click a tick to jump to its earliest start; Previous/Next event navigates the underlying unclustered starts, so clustering does not remove access. These markers inherit the minute summary precision and are navigation aids, not independently verified incident detections. Existing indexes remain compatible; no rebuild is required for these display changes.

## Studio 3 interaction fix

Clicking a floating node updates the IP selector and inspector on the right. Dragging beyond six pixels rearranges a node without selecting it; the dropdown remains available. The network now includes a bundled offline Streamlit component bridge, so keep the `network_component` directory when extracting. The observed-packets legend sits above the plot with reserved space; UTC time labels have their own bottom margin. Existing indexes remain compatible.
