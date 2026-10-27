# Introduction to Farm Flow attack vectors

This guide introduces the network attack categories covered by the Farm Flow reports. It explains what each attack is, how it operates, and the distinctions that help readers understand its behavior in a farm IoT network. The linked reports provide detailed analysis and mathematical models.

Farm networks connect sensors, actuators, gateways and application services. Attacks can redirect their communications, discover exposed services, or overwhelm the resources needed for monitoring and control.

## At a glance

| Attack category | Main mechanism | Typical objective |
| --- | --- | --- |
| ARP spoofing | Advertise a false local IP-to-MAC mapping | Redirect, intercept or interrupt communication |
| Port scanning | Probe ports or hosts to discover services | Identify potential entry points |
| Botnet DDoS | Coordinate traffic from many compromised devices | Overwhelm a service or network |
| HTTP flood | Repeatedly request web or API resources | Exhaust application capacity |
| ICMP flood | Send excessive network control messages | Consume processing or network capacity |
| MQTT flooding | Overload broker connections or messaging | Disrupt telemetry and message delivery |
| TCP flood | Overload transport processing or connection state | Reduce connection availability |
| UDP flood | Send excessive connectionless datagrams | Overwhelm packet handling or bandwidth |

These categories can overlap. For example, a botnet can generate an HTTP or UDP flood, and connection attempts against an MQTT broker can constitute a TCP flood.

## 1. ARP spoofing

**What it is.** Address Resolution Protocol (ARP) connects a local IPv4 address with an Ethernet MAC address. ARP spoofing advertises a false association, persuading another device to send frames to the attacker's MAC.

**How it works.** The attacker sends misleading ARP messages claiming that a legitimate IP belongs to its MAC. If a recipient accepts that claim into its ARP cache, subsequent frames can be redirected. The legitimate device can retain its original IP and MAC throughout the attack.

**Gateway and client variations.** The device being impersonated and the device receiving the false mapping play different roles:

| Variation | False association advertised | Recipient whose cache is poisoned | Potential effect |
| --- | --- | --- | --- |
| Gateway impersonation | Gateway IP → attacker MAC | Client | Client traffic intended for the gateway reaches the attacker |
| Client impersonation | Client IP → attacker MAC | Gateway | Gateway traffic intended for the client reaches the attacker |
| Both directions | Both associations above | Client and gateway | Traffic in both directions can pass through the attacker |

A gateway is the next hop used to reach another network and is commonly a router. When a client sends an internet-bound packet through a gateway, the packet retains its external destination IP while its local Ethernet frame is addressed to the gateway's MAC. Poisoning changes that local delivery decision.

**Important distinctions.** An attacker that forwards intercepted traffic can maintain communication while occupying an interception position. An attacker that drops it can interrupt communication. Poisoning both directions does not inherently disconnect both devices from every other device on the network. ARP spoofing normally operates within the local broadcast domain, such as a VLAN.

A repeated false claim can promote one attacker MAC; it does not require many changing MACs. Advertising a claim, having it accepted, and receiving redirected traffic are successive stages of the mechanism.

**Full report:** [ARP Spoofing Description and Model]

## 2. Port scanning

**What it is.** Port scanning discovers reachable network services by probing transport ports. It is a reconnaissance technique that can identify possible entry points before an attempted intrusion.

**How it works.** A scanner sends probes and interprets responses. In a TCP SYN scan, SYN/ACK generally indicates a responding listener, while a correlated reset generally indicates a closed port. Unanswered probes may reflect filtering or an unresponsive endpoint.

**Important distinctions.**

- A **vertical scan** probes many ports on one host.
- A **horizontal scan** probes a service across many hosts.
- A **slow scan** spreads probes over time; a **distributed scan** divides them among sources.
- TCP and UDP scans use different response behavior because UDP has no connection handshake.

Port breadth is central: repeatedly contacting one port differs from exploring many ports. Finding an open service identifies an opportunity for further investigation; it does not itself exploit that service. Authorized inventory tools also use scanning.

**Full report:** [Port Scanning Description and Model]

## 3. Botnet DDoS

**What it is.** A botnet is a group of compromised devices under coordinated control. A distributed denial of service (DDoS) attack uses multiple sources to overwhelm a target's resources.

**How it works.** Participating devices generate traffic or requests toward a shared target. Their combined demand can exceed network bandwidth, connection capacity or application processing capacity. Individual sources may send modest amounts while their aggregate load becomes disruptive.

**Important distinctions.** Botnet describes the organization of the participating devices; HTTP, TCP, UDP or another protocol describes the traffic mechanism. A botnet may flood a target directly or participate in a reflection attack. DDoS can also be generated without a botnet, so the terms are related rather than interchangeable.

Compromised farm IoT devices can be used as attack sources against other systems, while a farm service can be the target of traffic from elsewhere. The attacking devices and the victim therefore need not serve the same operational purpose or belong to the same network.

**Full report:** [Botnet DDoS Report and Appendices]

## 4. HTTP flood

**What it is.** An HTTP flood repeatedly requests web pages or API operations to consume application resources and degrade availability.

**How it works.** Requests such as GET and POST cause a server to parse messages, execute application logic, access storage or call downstream services. Excessive demand can fill queues and delay legitimate work.

**Important distinctions.** The cost of an operation matters as well as its frequency. A smaller number of expensive requests can create substantial load. Requests can appear ordinary individually, and attackers may reuse existing connections rather than repeatedly open new ones.

An HTTP flood operates at the application layer. TCP connection attempts against a web port represent an earlier protocol stage; an HTTP request requires application content. A single request may span several TCP segments, and one connection may carry many requests.

In a farm system, a telemetry API, dashboard or control endpoint can be targeted just as a public website can.

**Full report:** [HTTP Flood Report and Appendices]

## 5. ICMP flood

**What it is.** An ICMP flood sends excessive Internet Control Message Protocol messages. A common form uses Echo Requests, the messages used by ping.

**How it works.** A target receives requests and may generate Echo Replies. Receiving, inspecting and answering large volumes can consume host processing and network capacity.

**Important distinctions.** ICMP uses message types and codes rather than TCP or UDP ports. For IPv4, an Echo Request is type 8, code 0, and an Echo Reply is type 0, code 0.

A direct Echo Request flood sends traffic to the target itself. A reflected form directs replies from other systems toward the victim, typically by using the victim's address as the apparent request source. These are different traffic paths.

ICMP also supports legitimate diagnostics and network operation. The distinction between ordinary use and flooding depends on volume, persistence, context and resource demand.

**Full report:** [ICMP Flood Description and Model]

## 6. MQTT flooding

**What it is.** MQTT flooding overloads the connections or messaging functions of a publish/subscribe service. Clients publish messages on named topics, and a broker routes them to subscribed clients.

**How it works.** Pressure can arise at several stages:

- **Transport connections:** repeated attempts consume connection-handling resources.
- **MQTT sessions:** repeated CONNECT operations create authentication and session-management work.
- **Publishing:** excessive PUBLISH messages or large payloads consume processing, bandwidth and storage.
- **Subscriptions and delivery:** subscription churn or delivery to many subscribers increases routing and queue work.

**Important distinctions.** A broker manages and routes messages; it does not need to subscribe to every sensor topic as an ordinary client would. One incoming publication can cause many outgoing deliveries, depending on subscriptions.

Quality of Service (QoS) changes acknowledgment and delivery behavior, affecting resource demand. Session persistence and queued messages can extend the workload beyond the moment a message arrives.

A TCP SYN, MQTT CONNECT, MQTT CONNACK and MQTT PUBLISH belong to different stages. Connection flooding against a broker and application-message flooding can affect the same service through different mechanisms. In a farm network, disruption can delay sensor readings or commands distributed through the broker.

**Full report:** [MQTT Flood Description and Model]

## 7. TCP flood

**What it is.** A TCP flood generates excessive transport traffic to consume network or host resources. A SYN flood is a common form targeting connection establishment.

**How it works.** TCP normally establishes a connection through SYN, SYN/ACK and ACK. A listening service may retain pending state after sending SYN/ACK while waiting for the final ACK. Repeated incomplete attempts can consume that state and reduce capacity for legitimate connections.

**Important distinctions.** TCP flooding can impose different kinds of demand: pending connection state, established connection handling, packet processing or bandwidth. The affected resource depends on packet behavior and the target's implementation.

A SYN packet is a connection attempt, not an established connection. Varying source ports can create many apparent transport flows from one sender. A packet stream directed to a closed or unused port can still impose processing work without using a listening service's pending connection queue.

TCP is also the transport for many application protocols, so transport flooding can affect a service before any application message is exchanged.

**Full report:** [TCP Flood Description and Model]

## 8. UDP flood

**What it is.** A UDP flood sends excessive connectionless datagrams toward a host or service to consume packet-handling resources or bandwidth.

**How it works.** UDP does not establish a transport connection before delivery. A sender can transmit many datagrams without completing a handshake. The receiving system must handle the packets according to its network policy and any listening application.

**Important distinctions.** Packet rate, packet size and application cost create different kinds of pressure. Many small datagrams can stress packet processing, while larger datagrams can consume more bandwidth. Payloads may be meaningful application messages, malformed content or empty.

A **direct flood** sends datagrams toward the victim. A **reflection attack** causes other systems to send replies to the victim, typically by spoofing its source address. **Amplification** occurs when those responses are larger than the requests that induced them.

UDP itself supplies no acknowledgment or congestion-control mechanism; applications can add their own. A destination port identifies where a datagram is directed, while its payload determines whether it contains a valid application message.

**Full report:** [UDP Flood Description and Model]

## Further reading

The linked reports expand each introduction with Farm Flow observations, time-based analysis, mathematical models and supporting explanations.
