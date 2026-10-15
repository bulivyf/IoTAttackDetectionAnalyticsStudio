import unittest,tempfile,struct,shutil
from pathlib import Path
from indexer import build,read,selected,identities,message
from display_time import readable_frame
import pandas as pd

def packet():
    eth=bytes.fromhex('2ca17d72f19fe45f01b36c1b0800')
    ip=bytes.fromhex('450000280000000040060000c0a80105c0a80106')
    tcp=struct.pack('!HHIIHHHH',1883,6000,0,0,0x50100000>>16,100,0,0)
    return eth+ip+tcp

def write(path,t):
    b=packet();path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(struct.pack('<IHHIIII',0xa1b2c3d4,2,4,0,0,65535,1)+struct.pack('<IIII',t,0,len(b),len(b))+b)

class IndexTests(unittest.TestCase):
    def test_cross_file_duplicate_and_new_time(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a=root/'Normal'/'a.pcap';b=root/'TCP_Flood'/'b.pcap';c=root/'Normal'/'c.pcap'
            write(a,1660000000);write(b,1660000000);write(c,1660000005)
            db=build([a,b,c],root/'study.sqlite')
            cap=read(db,'SELECT * FROM captures')
            self.assertEqual(cap.original_packets.sum(),3);self.assertEqual(cap.retained_packets.sum(),2)
            self.assertEqual(cap.conflicting_duplicate_labels.sum(),1)
            f=selected(db,1659999995,1660000010,['Normal','TCP_Flood'])
            self.assertEqual(f.packets.sum(),2)
            idn=identities(f);pi=idn[(idn.ip=='192.168.1.5')&(idn.association=='Ethernet source association')]
            self.assertIn('Raspberry',pi.iloc[0].hardware)
            self.assertTrue((idn.loc[idn.association=='Ethernet destination association','hardware_score']<=40).all())
            self.assertEqual(len(selected(db,0,9999999999,[])),0)
    def test_topic_and_dates(self):
        p=b'\x30\x10\x00\x09soil/temp42'
        self.assertEqual(message(1883,123,p,'TCP',0)[2],'Soil/moisture messaging')
        f=readable_frame(pd.DataFrame({'filename_clock':[1660000000],'filename_start':[1660000000]}))
        self.assertIn('2022',f.iloc[0,0]);self.assertIn('UTC',f.iloc[0,1])
    def test_remote_identity_not_from_gateway(self):
        f=pd.DataFrame([dict(source='8.8.8.8',destination='192.168.1.5',source_mac='2c:a1:7d:72:f1:9f',destination_mac='e4:5f:01:b3:6c:1b',protocol='TCP',packets=3)])
        i=identities(f);self.assertEqual(i.loc[i.ip=='8.8.8.8','hardware_score'].max(),0)
if __name__=='__main__':unittest.main()
