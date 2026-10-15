"""Transparent heuristic scores, not calibrated probabilities."""
import ipaddress

VERSION='1.0.0'
OUI={
 'e4:5f:01':('Raspberry Pi',95),'dc:a6:32':('Raspberry Pi',95),'b8:27:eb':('Raspberry Pi',95),
 '4c:75:25':('Espressif board/interface',95),'30:83:98':('Espressif board/interface',95),
 '48:55:19':('Espressif board/interface',95),'a8:48:fa':('Espressif board/interface',95),
 '3c:71:bf':('Espressif board/interface',95),'b4:21:8a':('Arduino Yún candidate (Dog Hunter interface)',85),
 '2c:a1:7d':('CommScope/ARRIS gateway candidate',85)}
# MAC-bound working approximations accepted in this conversation. These are priors.
PRIORS={
 '192.168.1.1':('2c:a1:7d:72:f1:9f','Gateway/router',95,'Farm gateway',95),
 '192.168.1.4':('30:83:98:a2:a7:f7','Espressif board/interface',90,'Farm IoT node; purpose unresolved',60),
 '192.168.1.5':('e4:5f:01:b3:6c:1b','Raspberry Pi',98,'MQTT broker / farm control host',99),
 '192.168.1.6':('48:55:19:c1:a9:ce','Espressif board/interface',95,'Measurement / actuator-response node',95),
 '192.168.1.7':('4c:75:25:38:b4:f9','Espressif board/interface',95,'Measurement / actuator-response node',95),
 '192.168.1.9':('4c:75:25:37:7b:95','Espressif board/interface',95,'Measurement / actuator-response node',95),
 '192.168.1.10':('a8:48:fa:c1:7d:bd','Espressif board/interface',95,'Measurement / actuator-response node',95),
 '192.168.1.11':('30:83:98:a2:d4:2a','Espressif board/interface',95,'Measurement / actuator-response node',95),
 '192.168.1.12':('3c:71:bf:c7:fa:c0','Espressif board/interface',95,'Temperature / soil messaging intermediary',95),
 '192.168.1.13':('b4:21:8a:f0:20:db','Arduino Yún candidate (Dog Hunter interface)',85,'Multichannel measurement / buzzer-feedback node',95)}
SERVICES={
 'connectivity-check.ubuntu.com':('Internet connectivity check',99),
 'ports.ubuntu.com':('Ubuntu package distribution',99),
 'changelogs.ubuntu.com':('Ubuntu release/changelog service',95),
 'deb.nodesource.com':('Node.js package distribution',95),
 'ppa.launchpadcontent.net':('Launchpad package distribution',95),
 'cdn.fwupd.org':('Firmware-update distribution',95),
 'odrs.gnome.org':('GNOME software-review service',95),
 'api.snapcraft.io':('Snap software-store API',95)}
def scope(ip):
    a=ipaddress.ip_address(ip)
    if a.is_multicast: return 'Multicast'
    if a.version==4 and any(a in ipaddress.ip_network(n) for n in ['10.0.0.0/8','172.16.0.0/12','192.168.0.0/16']): return 'Local/private'
    if a.version==6 and (a.is_private or a.is_link_local): return 'Local/private'
    return 'External/other'
