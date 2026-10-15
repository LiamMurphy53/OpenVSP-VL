"""Custom GUI controls retain original global and structural parameter owners."""
import base64
import unittest
import test_native
import test_custom_scripts

class GlobalCustomBindings(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    template=test_custom_scripts.CustomScripts.template

    def test_global_and_structural_inputs_use_current_native_bindings(self):
        v=self.v;prop=v.AddFeaProperty(v.FEA_SHELL);v.SetContainerName(prop,'Bound shell')
        mach=v.FindParm(v.FindContainer('VSPAEROSettings',0),'MachStart','VSPAERO')
        thickness=v.FindParm(prop,'Thickness','FeaProperty');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        script=self.template().replace('int LengthSlider;','int GlobalInput;int StructuralInput;int LengthSlider;')
        script=script.replace('void InitGui()\n{','void InitGui()\n{\n GlobalInput=AddGui(GDEV_SLIDER_INPUT,"Mach start");StructuralInput=AddGui(GDEV_SLIDER_INPUT,"Shell thickness");')
        script=script.replace('void UpdateGui()\n{','void UpdateGui()\n{\n UpdateGui(GlobalInput,FindParm(FindContainer("VSPAEROSettings",0),"MachStart","VSPAERO"));\n UpdateGui(StructuralInput,FindParm(FindContainer("Bound shell",0),"Thickness","FeaProperty"));')
        state,path=self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_SCRIPT',name='Global controls',content=base64.b64encode(script.encode()).decode()))
        child=next(c for c in state['components'] if c['name']=='Global controls');gid=child['id']
        controls={r['parameter']['label']:r for r in child['customExternalControls']}
        self.assertEqual(controls['Mach start']['owner'],'VSPAEROSettings')
        self.assertEqual(controls['Shell thickness']['owner'],'Bound shell')
        geometry={c['id']:c['surfaces'] for c in state['components']}
        for label,pid,value in [('Mach start',mach,.2),('Shell thickness',thickness,.05)]:
            row=controls[label];self.assertEqual(row['parameter']['id'],pid)
            state,path=self.worker(dict(action='mutate',operation='custom-control-parameter',geom=gid,index=row['index'],id=pid,value=value),path)
            cold,_=self.worker(dict(action='state'),path)
            for result in (state,cold):
                actual=next(c for c in result['components'] if c['id']==gid)
                control=next(r for r in actual['customExternalControls'] if r['parameter']['label']==label)
                self.assertEqual(control['parameter']['id'],pid);self.assertAlmostEqual(control['parameter']['value'],value)
                self.assertNotIn(pid,{p['id'] for p in actual['params']})
                self.assertEqual({c['id']:c['surfaces'] for c in result['components']},geometry)
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        self.assertAlmostEqual(v.GetParmVal(mach),.2);self.assertAlmostEqual(v.GetParmVal(thickness),.05)

if __name__=='__main__':unittest.main()
