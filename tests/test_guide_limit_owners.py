"""Guided analysis limits must come from the true manager and parameter group."""
import unittest
import test_native
import native_guides

class GuideOwners(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown

    def test_limits_ignore_same_name_containers_and_parameter_groups(self):
        v=self.v
        # Original API proxy presents a colliding last-listed container, as can
        # occur with user controls. Exact owner/group resolution must ignore it.
        class Collision:
            def __getattr__(self,name):return getattr(v,name)
            def FindContainers(self):return [*v.FindContainers(),'collision']
            def GetContainerName(self,c):return 'Vehicle' if c=='collision' else v.GetContainerName(c)
            def FindContainerParmIDs(self,c):return ['wrong'] if c=='collision' else v.FindContainerParmIDs(c)
            def GetParmName(self,p):return 'NumMassSlices' if p=='wrong' else v.GetParmName(p)
            def GetParmLowerLimit(self,p):return 999 if p=='wrong' else v.GetParmLowerLimit(p)
            def GetParmUpperLimit(self,p):return 1000 if p=='wrong' else v.GetParmUpperLimit(p)
        proxy=Collision()
        for analysis,owner,group,names in [
            ('MassProp',v.GetVehicleID(),'MassProperties',{'NumMassSlices':'NumMassSlices'}),
            ('PlanarSlice',v.GetVehicleID(),'PSlice',{'NumSlices':'NumPlanerSlices','StartVal':'PlanarStartLocation','EndVal':'PlanarEndLocation'}),
            ('WaveDrag',native_guides.native_managers.manager(v,'WaveDragSettings'),'WaveDrag',{'NumSlices':'NumSlices','Mach':'MachNumber'}),
            ('ParasiteDrag',native_guides.native_managers.manager(v,'ParasiteDragSettings'),'ParasiteDrag',{'Vinf':'Vinf','Altitude':'Alt'})]:
            fields=[dict(name=n,index=0,values=[0],type=0) for n in names]
            native_guides.annotate(proxy,analysis,fields)
            for field in fields:
                pid=v.FindParm(owner,names[field['name']],group)
                self.assertTrue(pid,(analysis,field['name']))
                self.assertEqual((field['min'],field['max']),(v.GetParmLowerLimit(pid),v.GetParmUpperLimit(pid)))
