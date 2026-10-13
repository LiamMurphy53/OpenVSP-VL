"""Actuator drivers: native validation, XML persistence and derived values."""
import itertools
import json
import sys
import unittest
import xml.etree.ElementTree as ET
import test_native
import native_preview
import native_references
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the native Python runtime.')
class PropDrivers(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def disk(self):
        v=self.v;p=v.AddGeom('PROP');v.SetParmValUpdate(p,'PropMode','Design',v.PROP_DISK);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        return v.FindActuatorDisk(0)

    def test_all_native_combinations_persist_and_calculate_like_independent_sdk(self):
        v=self.v;cid=self.disk();source=self.model.read_bytes();combinations=native_preview.prop_driver_combinations(v)
        self.assertEqual(len(combinations),50)
        self.assertEqual(len({tuple(c) for c in combinations}),50)
        for choices in combinations:
            with self.subTest(choices=choices):
                state,saved=self.worker(dict(action='mutate',operation='rotor-disk-drivers',id=cid,choices=choices))
                disk=next(d for d in state['tools']['disks'] if d['id']==cid)
                self.assertEqual(disk['driverChoices'],choices)
                # Independently edit the original native document and let the
                # official SDK decode/update its native driver equations.
                tree=ET.parse(self.model);node=next(n for n in tree.findall('.//VSPAEROSettings/Rotor') if n.findtext('ParmContainer/ID')==cid)
                node.find('DriverGroup/ChoiceVec').text=', '.join(map(str,choices))+', '
                direct=self.path/'independent.vsp3';tree.write(direct,encoding='utf-8',xml_declaration=True)
                v.ClearVSPModel();v.ReadVSPFile(str(direct));v.Update()
                expected={v.GetParmName(p):v.GetParmVal(p) for p in v.FindContainerParmIDs(cid)}
                self.assertEqual({p['name']:p['value'] for p in disk['params']},expected)
                actual_active={d['value'] for d in disk['drivers'] if next(p for p in disk['params'] if p['id']==d['parameter'])['active']}
                self.assertEqual(actual_active,set(choices))
                self.assertEqual(ET.parse(saved).find('.//VSPAEROSettings/Rotor/DriverGroup/ChoiceVec').text,node.findtext('DriverGroup/ChoiceVec'))
        self.assertEqual(self.model.read_bytes(),source)

    def test_invalid_choices_preserve_native_model(self):
        cid=self.disk();source=self.model.read_bytes()
        invalid=[list(c) for c in itertools.combinations(range(9),3) if list(c) not in native_preview.prop_driver_combinations(self.v)]
        invalid.extend([[0,0,1],[0,1],[-1,1,2],[0,1,9],[True,1,2],['0',1,2]])
        for choices in invalid:
            with self.subTest(choices=choices),self.assertRaises(ValueError):
                self.worker(dict(action='mutate',operation='rotor-disk-drivers',id=cid,choices=choices))
        self.assertEqual(self.model.read_bytes(),source)

    def test_driving_values_and_hub_controls_use_native_dependencies(self):
        v=self.v;cid=self.disk();state,saved=self.worker(dict(action='mutate',operation='rotor-disk-drivers',id=cid,choices=[0,3,6]))
        disk=state['tools']['disks'][0];params={p['name']:p for p in disk['params']}
        for name in ('RotorCP','RotorDiameter','RotorHubDiameter'):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'derives'):
                self.worker(dict(action='mutate',operation='parameter',id=params[name]['id'],value=1),saved)
        state,saved=self.worker(dict(action='mutate',operation='parameter',id=params['RotorThrust']['id'],value=2000),saved)
        state,saved=self.worker(dict(action='mutate',operation='parameter',id=params['RotorPower']['id'],value=50000),saved)
        v.ClearVSPModel();v.ReadVSPFile(str(saved));v.Update()
        self.assertEqual(v.GetParmVal(params['RotorThrust']['id']),2000);self.assertEqual(v.GetParmVal(params['RotorPower']['id']),50000)
        state,saved=self.worker(dict(action='mutate',operation='parameter',id=params['AutoHubDiaFlag']['id'],value=0),saved)
        self.assertTrue(next(p for p in state['tools']['disks'][0]['params'] if p['name']=='RotorHubDiameter')['active'])
        state,saved=self.worker(dict(action='mutate',operation='parameter',id=params['RotorHubDiameter']['id'],value=.25),saved)
        self.assertEqual(next(p['value'] for p in state['tools']['disks'][0]['params'] if p['name']=='RotorHubDiameter'),.25)

    def test_manual_hub_extremes_and_diameter_changes_match_native_clamping(self):
        v=self.v;cid=self.disk();prop=next(g for g in v.FindGeoms() if v.GetGeomTypeName(g)=='Propeller')
        ids={v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)};auto=ids['AutoHubDiaFlag'];hub=ids['RotorHubDiameter']
        source=self.model.read_bytes();state,saved=self.worker(dict(action='mutate',operation='parameter',id=auto,value=0))
        for value in [0,1,100,1e12]:
            with self.subTest(value=value):
                prior=saved.read_bytes()
                state,saved=self.worker(dict(action='mutate',operation='parameter',id=hub,value=value),saved)
                direct=self.path/'hub-direct.vsp3';direct.write_bytes(prior)
                v.ClearVSPModel();v.ReadVSPFile(str(direct));v.Update();v.SetParmValUpdate(hub,value);v.GetNumActuatorDisks()
                expected={v.GetParmName(p):v.GetParmVal(p) for p in v.FindContainerParmIDs(cid)}
                actual={p['name']:p for p in state['tools']['disks'][0]['params']}
                self.assertEqual({n:p['value'] for n,p in actual.items()},expected)
                self.assertEqual(actual['RotorHubDiameter']['max'],v.GetParmUpperLimit(hub))
                self.assertEqual(actual['RotorHubDiameter']['effectiveMax'],expected['RotorDiameter'])
                self.assertLessEqual(actual['RotorHubDiameter']['value'],actual['RotorHubDiameter']['effectiveMax'])
        diameter=v.FindParm(prop,'Diameter','Design')
        state,saved=self.worker(dict(action='mutate',operation='parameter',id=diameter,value=.5),saved)
        actual={p['name']:p for p in state['tools']['disks'][0]['params']}
        self.assertEqual(actual['RotorHubDiameter']['value'],.5);self.assertEqual(actual['RotorHubDiameter']['effectiveMax'],.5)
        state,saved=self.worker(dict(action='mutate',operation='parameter',id=auto,value=1),saved)
        actual={p['name']:p for p in state['tools']['disks'][0]['params']};self.assertFalse(actual['RotorHubDiameter']['active'])
        v.ClearVSPModel();v.ReadVSPFile(str(saved));v.Update();v.GetNumActuatorDisks();self.assertEqual(actual['RotorHubDiameter']['value'],v.GetParmVal(hub))
        self.assertEqual(self.model.read_bytes(),source)
