import math
from pathlib import Path
import struct
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aero_io import read_adb, read_flow_plane


def database(endian='<',version=3):
    def pack(fmt,*values):return struct.pack(endian+fmt,*values)
    header=pack('8i6f',-123789453 if version==3 else -123789456,1,0,0,1,3,1,3,10,1,10,0,0,0)
    header+=pack('ii',1,7)+b'Wing\0'.ljust(100,b'\0')+pack('i',4)
    geometry=pack('6if',1,2,3,4,7,0,.5)+pack('9f',0,0,0,1,0,0,0,1,0)
    geometry+=pack('i',1)+(pack('i',1) if version==3 else b'')+pack('11d',*[0.]*11)
    if version==3:geometry+=pack('7d',*[0.]*7)
    geometry+=pack('3i',0,0,0) # mesh levels, Kutta edges/nodes
    geometry+=pack('2i',1,3)+pack('9f',0,0,0,1,0,0,0,1,0)+pack('9f',0,0,0,1,0,0,1,0,0)+pack('2i',1,1)
    content=header
    for index in (1,2):
        content+=geometry+pack('5f',.1,math.radians(index*3),0,-2,2)
        content+=pack('14d',*[0.]*14) # 5 loop doubles and 3*3 edge forces
        content+=pack('3f',index*.25,index*.1,index*.5)
        content+=pack('2i',1,3)+pack('d',.5)+pack('i',2)+pack('6d',0,1,0,10,1,2)
        content+=pack('f',index*.2)
    return content


class AeroFiles(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def write(self,content):
        path=self.folder/'wing.adb';path.write_bytes(content)
        Path(str(path)+'.cases').write_text('.1 3 0 Case: 1\n.1 6 0 Case: 2\n')
        return path
    def test_native_records_preserve_cases_controls_rotors_and_endianness(self):
        for endian,version in [('<',3),('>',3),('<',2)]:
            mesh=read_adb(self.write(database(endian,version)),2)
            self.assertEqual(mesh['case'],2);self.assertEqual(mesh['elements'][0]['nodes'],[0,1,2])
            self.assertEqual(mesh['groups'][0]['name'],'Wing');self.assertEqual(mesh['fields'][0]['values'],[.5])
            self.assertAlmostEqual(mesh['conditions']['alpha'],6,places=5)
            self.assertAlmostEqual(mesh['deflections'][0],.4,places=6)
            self.assertEqual(mesh['wakes'][0]['points'][-1],(10,1,2))
            self.assertEqual(len(mesh['controls'][0]['points']),3)
    def test_invalid_native_database_fails_explicitly(self):
        for content in [database()[:70],database()[:-10],b'not an adb',database().replace(struct.pack('<3f',.5,.2,1),struct.pack('<3f',float('nan'),.2,1))]:
            with self.assertRaises(ValueError):read_adb(self.write(content),2)
        for case in (0,3,True,1.5):
            with self.assertRaises(ValueError):read_adb(self.write(database()),case)
        path=self.write(database());sidecar=Path(str(path)+'.cases');sidecar.unlink();sidecar.symlink_to(self.folder/'other')
        with self.assertRaises(ValueError):read_adb(path)
    def test_flow_plane_keeps_native_nodal_values_and_ids(self):
        path=self.folder/'wing.case.1.quad.1.dat'
        path.write_text('2 0 100 200\n4 1\n10 0 0 0 100 2 3 -.1\n20 1 0 0 90 3 4 -.2\n30 1 0 1 80 4 5 -.3\n40 0 0 1 70 5 6 -.4\n7 10 20 30 40\n')
        mesh=read_flow_plane(path)
        self.assertEqual(mesh['referenceSpeed'],100);self.assertEqual(mesh['solverVelocityScale'],200)
        self.assertEqual(mesh['nodeIDs'],[10,20,30,40]);self.assertEqual(mesh['elements'][0]['id'],7)
        self.assertEqual(mesh['fields'][0]['nodeValues'],[-.1,-.2,-.3,-.4])
        self.assertAlmostEqual(mesh['fields'][0]['values'][0],-.25)
        path.write_text(path.read_text().replace('7 10 20 30 40','7 10 20 30 99'))
        with self.assertRaises(ValueError):read_flow_plane(path)

if __name__=='__main__':unittest.main()
