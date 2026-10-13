"""Explicit native log messages, full-log review, bounds and saved-run recovery."""
import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import native_diagnostics as diagnostics
import native_service as service

class NativeDiagnostics(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name);diagnostics.CACHE.clear()
 def tearDown(self):self.temp.cleanup();diagnostics.CACHE.clear()
 def test_native_messages_group_without_reinterpreting_quality_or_changing_log(self):
  path=self.folder/'engine.log';raw=b'Working on level 2\rERROR: Incomplete IGES Loop \nERROR: Incomplete IGES Loop \nWARNING: Native warning\nInvalid reason 17\nInvalid reason 17\nNOT Water Tight : 16 Border Edges, 0 Edges > 2 Tris\nIs Water Tight\n';path.write_bytes(raw)
  data=diagnostics.scan(path);self.assertEqual(data['totalMessages'],6)
  self.assertEqual([(m['severity'],m['text'],m['count'],m['firstLine']) for m in data['messages']],[('error','ERROR: Incomplete IGES Loop',2,2),('warning','WARNING: Native warning',1,4),('review','Invalid reason 17',2,5),('review','NOT Water Tight : 16 Border Edges, 0 Edges > 2 Tris',1,7)])
  self.assertNotIn('quality',data);self.assertEqual(path.read_bytes(),raw)
 def test_message_limits_preserve_total_occurrences_and_abbreviation(self):
  path=self.folder/'engine.log';path.write_text('ERROR: '+('x'*1200)+'\nERROR: second\nERROR: third\nERROR: third\n')
  data=diagnostics.scan(path,max_groups=2);self.assertEqual(data['totalMessages'],4);self.assertEqual(data['omittedOccurrences'],2);self.assertTrue(data['abbreviated']);self.assertEqual(len(data['messages'][0]['text']),1000)
 def test_missing_symlink_and_changed_saved_log_are_handled(self):
  path=self.folder/'engine.log';self.assertFalse(diagnostics.saved(path)['available']);path.write_text('ERROR: first\n');first=diagnostics.saved(path);self.assertEqual(first['totalMessages'],1)
  path.write_text('ERROR: first\nERROR: second\n');self.assertEqual(diagnostics.saved(path)['totalMessages'],2)
  link=self.folder/'link';link.symlink_to(path);self.assertFalse(diagnostics.saved(link)['available'])
 def test_saved_run_reviews_early_errors_outside_tail_and_survives_reopen(self):
  old=service.WORK,service.JOBS
  try:
   service.WORK=self.folder;service.JOBS={};jid='e'*32;run=self.folder/'jobs'/jid;run.mkdir(parents=True)
   (run/'request.json').write_text(json.dumps(dict(name='SurfaceIntersection',revision='fixture')));(run/'response.json').write_text(json.dumps(dict(analysis='SurfaceIntersection',results=[])))
   log=run/'engine.log';raw=('ERROR: Incomplete STEP Loop\n'+'Native progress\n'*3000).encode();log.write_bytes(raw)
   first=service.job_state(jid);self.assertNotIn('Incomplete STEP Loop',first['log']);self.assertEqual(first['diagnostics']['messages'][0]['text'],'ERROR: Incomplete STEP Loop');self.assertEqual(first['status'],'complete')
   service.JOBS={};second=service.job_state(jid);self.assertEqual(second['diagnostics'],first['diagnostics']);self.assertEqual(log.read_bytes(),raw)
  finally:service.WORK,service.JOBS=old
