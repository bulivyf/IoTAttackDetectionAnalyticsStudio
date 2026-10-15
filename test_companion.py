import json,unittest
from types import SimpleNamespace
import numpy as np
import pandas as pd
from data import Table,load_bytes,catalog
from analysis import execute
from companion import run_turn

class ResearchTests(unittest.TestCase):
    def tables(self):
        df=pd.DataFrame({'ip':['a','a','b','b','b'],'time':[0,60,120,180,240],'x':[1,2,3,4,5],'y':[3,5,7,9,11],'packets':[1,2,3,4,5]})
        return {'test':Table('test','test','synthetic.csv','abc',df,[])}
    def test_scope_applies_to_model_and_catalog(self):
        scope={'test':[dict(column='ip',op='eq',value='a')]}
        r,_=execute(self.tables(),{'table':'test','operation':'aggregate','group_by':['ip'],'y':'packets'},scope)
        self.assertEqual(r['rows'],[{'ip':'a','value':3}]);self.assertEqual(catalog(self.tables(),scope)[0]['rows'],2)
        self.assertTrue(all(x['ip']=='a' for x in catalog(self.tables(),scope)[0]['sample']))
    def test_ols_known_solution(self):
        r,_=execute(self.tables(),dict(table='test',operation='linear_model',x='x',y='y'))
        self.assertAlmostEqual(r['model']['slope'],2);self.assertAlmostEqual(r['model']['intercept'],1)
        self.assertAlmostEqual(r['model']['r_squared'],1)
    def test_coverage_required(self):
        with self.assertRaises(ValueError):execute(self.tables(),dict(table='test',operation='rate_model',y='packets'))
        r,_=execute(self.tables(),dict(table='test',operation='rate_model',y='packets',exposure_seconds=30))
        self.assertEqual(r['model']['rate_per_second'],0.5)
    def test_unsupported_code(self):
        with self.assertRaises(ValueError):execute(self.tables(),dict(table='test',operation='exec',code='anything'))
    def test_json_adapters(self):
        blob=json.dumps({'version':'timeline-1.0','nodes':{},'captures':[{'file':'x'}],'bins':[{'time':1,'packets':3}]}).encode()
        self.assertTrue(any(t.name.endswith('/ bins') for t in load_bytes('timeline.json',blob)))
    def test_zero_mad(self):
        tables=self.tables();tables['test'].frame['y']=1
        with self.assertRaises(ValueError):execute(tables,dict(table='test',operation='robust_anomaly',y='y'))
    def test_join_does_not_multiply_counts(self):
        tables=self.tables()
        tables['inventory']=Table('inventory','inventory','inventory.csv','def',pd.DataFrame({'ip':['a','b'],'hardware':['Pi','ESP']}),[])
        r,_=execute(tables,dict(table='test',join_table='inventory',join_key='ip',operation='aggregate',group_by=['right__hardware'],y='packets'))
        self.assertEqual(sum(v['value'] for v in r['rows']),15)
        tables['inventory'].frame=pd.DataFrame({'ip':['a','a'],'hardware':['Pi','ESP']})
        with self.assertRaises(ValueError):execute(tables,dict(table='test',join_table='inventory',join_key='ip',operation='summary'))
    def test_responses_tool_round_trip(self):
        calls=[]
        class Fake:
            def create(self,**kwargs):
                calls.append(kwargs)
                if len(calls)==1:
                    tool=SimpleNamespace(type='function_call',name='analyse_data',call_id='c1',arguments=json.dumps({'table':'test','operation':'aggregate','group_by':['ip'],'y':'packets'}))
                    return SimpleNamespace(output=[tool],output_text='',usage=None)
                return SimpleNamespace(output=[],output_text='IP b has 12 packets [Q1].',usage=None)
        client=SimpleNamespace(responses=Fake())
        text,results,_=run_turn(self.tables(),'Count by IP',[],{},'unused','test-model',client=client)
        self.assertEqual(len(results),1);self.assertEqual(results[0]['id'],'Q1')
        self.assertEqual(results[0]['rows'][0],{'ip':'b','value':12})
        self.assertFalse(calls[0]['store']);self.assertIn('[Q1]',text)
        self.assertTrue(any(isinstance(m,dict) and m.get('type')=='function_call_output' for m in calls[1]['input']))

if __name__=='__main__':unittest.main()
