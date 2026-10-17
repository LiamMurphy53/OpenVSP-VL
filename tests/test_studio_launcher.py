"""Real localhost startup, native loading and safe server reuse."""
import json
import os
from pathlib import Path
import signal
import socket
import sys
import tempfile
import unittest
from urllib.request import urlopen
import studio_launcher as launcher


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native runtime.')
class StudioLauncher(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='studio launch with spaces ')
        self.workspace=Path(self.temp.name)/'aircraft workspace';self.pid=None

    def tearDown(self):
        if self.pid:
            try:os.kill(self.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            launcher._started_processes.pop(self.pid).wait(timeout=10)
        self.temp.cleanup()

    def port(self):
        with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]

    def test_native_start_reuse_and_saved_model_are_exact(self):
        port=self.port();info,created=launcher.start(port,self.workspace);self.pid=info['processID']
        self.assertTrue(created);self.assertEqual(info['engineVersion'],'OpenVSP 3.52.2')
        with urlopen(f'http://127.0.0.1:{port}/api/state',timeout=20) as response:state=json.load(response)
        self.assertEqual(state['version'],'OpenVSP 3.52.2')
        before=(self.workspace/'aircraft.vsp3').read_bytes()
        again,created=launcher.start(port,self.workspace)
        self.assertFalse(created);self.assertEqual(again['processID'],self.pid)
        self.assertEqual((self.workspace/'aircraft.vsp3').read_bytes(),before)
        self.assertIsNone(launcher.health(port,self.workspace/'different'))

    def test_occupied_port_is_not_replaced(self):
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1',0));occupied.listen()
            with self.assertRaisesRegex(ValueError,'already in use'):
                launcher.start(occupied.getsockname()[1],self.workspace)
            self.assertFalse((self.workspace/'studio-launch.json').exists())

    def test_same_workspace_on_second_port_is_rejected(self):
        port=self.port();info,_=launcher.start(port,self.workspace);self.pid=info['processID']
        with self.assertRaisesRegex(ValueError,'could not start'):
            launcher.start(self.port(),self.workspace)
        self.assertEqual(launcher.health(port,self.workspace)['processID'],self.pid)

    def test_app_launcher_is_relative_and_modern(self):
        import subprocess,plistlib
        bundle=launcher.ROOT.parent.parent if launcher.ROOT.parent.name=='Resources' else launcher.ROOT/'OpenVSP Studio.app/Contents'
        info=plistlib.loads((bundle/'Info.plist').read_bytes())
        self.assertEqual(info['CFBundleDisplayName'],'OpenVSP Studio')
        result=subprocess.run([str(bundle/'MacOS/launch'),'--check'],cwd='/',capture_output=True,text=True,timeout=35)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('OpenVSP 3.52.2',result.stdout)


if __name__=='__main__':unittest.main()
