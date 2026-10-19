"""Separate unusable solver fields from malformed flow-plane geometry."""
import unittest,tempfile
from pathlib import Path
from aero_io import read_flow_plane

class NonfiniteFlow(unittest.TestCase):
    def test_invalid_solver_values_have_explicit_diagnostic(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'native.dat'
            for column in range(3,7):
                for value in ['nan','inf','-inf']:
                    with self.subTest(column=column,value=value):
                        fields=['0','0','0','1','0','0','2'];fields[column]=value
                        p.write_text('1 0 1 1\n4 1\n'+''.join(str(i)+' '+' '.join(fields)+'\n' for i in range(1,5))+'1 1 2 3 4\n');before=p.read_bytes()
                        with self.assertRaisesRegex(ValueError,'native solver wrote nonfinite velocity or pressure at node 1'):read_flow_plane(p)
                        self.assertEqual(p.read_bytes(),before)

    def test_bad_geometry_and_valid_fields_stay_distinct(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'native.dat';text='1 0 1 1\n4 1\n'+''.join(f'{i} {i} 0 0 1 0 0 2\n' for i in range(1,5))+'1 1 2 3 4\n';p.write_text(text);m=read_flow_plane(p);self.assertEqual(m['fields'][0]['nodeValues'],[2.]*4)
            p.write_text(text.replace('1 1 0 0','1 nan 0 0'))
            with self.assertRaisesRegex(ValueError,'coordinates or duplicate'):read_flow_plane(p)

if __name__=='__main__':unittest.main()
