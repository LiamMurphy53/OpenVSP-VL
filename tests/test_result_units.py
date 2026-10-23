"""Known native dimensions and study metadata do not infer units for unknown fields."""
import unittest
from unittest.mock import patch
from native_result_units import result_unit
import native_studies

class ResultUnits(unittest.TestCase):
    def test_geometry_units_distinguish_mass_inertia_area_and_coordinates(self):
        for axis in ['xx','yy','zz','xy','xz','yz']:
            self.assertEqual(result_unit('Mass_Properties','Comp_I'+axis),'model mass × model length²')
        for record,name,unit in [('Mass_Properties','Total_Mass','model mass'),('Mass_Properties','Total_CG','model length'),('Comp_Geom','Tag_Theo_Area','model length²'),('Projection','Area','model length²'),('Slice','Slice_Area_Center','model length'),('Slice','Axis_Vector','dimensionless')]:self.assertEqual(result_unit(record,name),unit)
        self.assertEqual(result_unit('Unknown','Area'),'');self.assertEqual(result_unit('Mass_Properties','Unknown_Ixx'),'')

    def test_study_catalogue_includes_known_geometry_mesh_and_flow_units(self):
        batch=dict(cases=[dict(stages=[dict(index=0,status='complete',job='job')])]);result=dict(results=[dict(name='Slice',index=0,entries=[dict(name='Slice_Area',index=0,type=2,values=[1.,2.])])],meshSummary=dict(nodes=12,elements=4),flowPlanes=[dict(file='native.flow',nodes=9)])
        with patch.object(native_studies,'batch_state',return_value=batch),patch.object(native_studies.service,'job_state',return_value=dict(result=result)):
            fields=native_studies.result_fields('study','batch')
        units={f['field']:f['unit'] for f in fields};self.assertEqual(units['Slice_Area'],'model length²');self.assertEqual(units['Nodes'],'count');self.assertEqual(units['Cp'],'dimensionless');self.assertEqual(units['X'],'model length');self.assertEqual(units['U'],'native length/s')
