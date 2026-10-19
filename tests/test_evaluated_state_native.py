"""Native record dimensions must match the actual saved computation."""
import sys,unittest,json,hashlib
import test_native
import native_evaluated_state as state
import native_flow_reader as reader

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native runtime.')
class NativeEvaluatedState(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_well_formed_but_wrong_native_records_are_rejected(self):
        v=self.v
        values=dict(GeomSet=-1,ThinGeomSet=0,RefFlag=1,WingID=self.gid,AlphaStart=4.,AlphaNpts=1,MachStart=.1,MachNpts=1,NCPU=1,NumTimeSteps=4,TimeStepSize=.02,NumWakeNodes=8,WakeNumIter=3,UnsteadyType=v.STABILITY_Q_ANALYSIS)
        result,path=self.worker(dict(action='analysis',name='VSPAEROSweep',inputs=[dict(name=n,values=[x]) for n,x in values.items()]))
        self.assertEqual(result['evaluatedStateCapture']['mode'],'captured')
        database=path.with_suffix('.adb');companion=path.with_suffix('.studio-state');original=companion.read_text();before=hashlib.sha256(database.read_bytes()).hexdigest();writer=state.validate(database)['binding']['writer']
        for kind in ['grid','surfaces','time','edges']:
            with self.subTest(kind=kind):
                rows=original.splitlines()
                if kind in ('grid','surfaces'):
                    fields=rows[1].split();index=2 if kind=='grid' else 4;fields[index]=str(int(fields[index])+1 if kind=='grid' else int(fields[index])-1);rows[1]=' '.join(fields)
                    if kind=='grid':
                        # Keep the companion structurally valid while disagreeing with the native grid.
                        for i,line in enumerate(rows[2:],2):
                            if line.startswith('L '):
                                parts=line.split();parts[1]=str(int(parts[1])+1);rows[i]=' '.join(parts)
                            elif line.startswith('R '):
                                parts=line.split();parts[2]=str(int(parts[2])+1);rows[i]=' '.join(parts)
                elif kind=='edges':
                    i=next(i for i,line in enumerate(rows) if line.startswith('L '));parts=rows[i].split();count=int(parts[2]);parts[2]=str(count-1);rows[i]=' '.join(parts);del rows[i+count]
                else:
                    for i,line in enumerate(rows):
                        if line.startswith('R '):
                            fields=line.split();fields[5]=(float.fromhex(fields[5])*2).hex();rows[i]=' '.join(fields)
                companion.write_text('\n'.join(rows)+'\n');state.seal(database,writer)
                self.assertIsNotNone(state.validate(database),'Binding is structurally valid; the native engine must reject the actual record mismatch.')
                with self.assertRaisesRegex(ValueError,'reader exited with status 2'):reader.run(v,database.with_suffix('.vspaero'),True,v.STABILITY_Q_ANALYSIS)
                self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(),before)
        companion.write_text(original);state.seal(database,writer)

if __name__=='__main__':unittest.main()
