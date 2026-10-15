"""Folder-based dataset selection, not attack detection."""
from pathlib import Path
import re

CATEGORIES=['Normal','Arp_Spoofing','BotNet_DDOS','HTTP_Flood','ICMP_Flood','MQTT_Flood','Port_Scanning','TCP_Flood','UDP_Flood']
ALIASES={re.sub(r'[^a-z0-9]','',s.lower()):s for s in CATEGORIES}

def capture_tags(path):
    # Full path works when the user selects Captures, a month or an attack folder.
    parts=Path(path).parts
    months=[p for p in parts[:-1] if re.fullmatch(r'(0[1-9]|1[0-2])[_-]20\d{2}',p)]
    categories=[ALIASES[re.sub(r'[^a-z0-9]','',p.lower())] for p in parts[:-1] if re.sub(r'[^a-z0-9]','',p.lower()) in ALIASES]
    return months[-1].replace('-','_') if months else 'Unspecified month',categories[-1] if categories else 'Unclassified'

def filtered(paths,months,include,exclude):
    return [p for p in paths if capture_tags(p)[0] in months and capture_tags(p)[1] in include and capture_tags(p)[1] not in exclude]
