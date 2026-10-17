"""Saved plane downloads retain native data and work as HTTP attachments."""
import csv,io,json,threading,unittest
from urllib.parse import urlsplit,parse_qs
from urllib.request import urlopen
import test_native,native_service as service,server
from http.server import ThreadingHTTPServer

class PlaneDownloads(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    def setUp(self):
        test_native.NativeIntegration.setUp(self)
        self.old=(service.WORK,service.MODEL,service.REVISION)
        service.WORK=self.path;service.MODEL=self.model;service.REVISION='plane-download-test'
        points=[self.v.vec3d(i*.013,(i%17)*.029,2+(i%11)*.041) for i in range(305)]
        self.cloud=self.v.CreatePtCloudGeomFromPts(points,'Download plane');self.v.Update();self.v.WriteVSPFile(str(self.model),self.v.SET_ALL)
    def tearDown(self):
        service.WORK,service.MODEL,service.REVISION=self.old
        test_native.NativeIntegration.tearDown(self)
    def query(self):return service.query(dict(operation='cloud-fit-plane',geom=self.cloud,revision=service.REVISION))
    def test_json_csv_http_attachments_match_all_native_points_and_offsets(self):
        before=self.model.read_bytes();data=self.query();self.assertEqual(data['pointCount'],305)
        http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            bodies={}
            for fmt,url in data['exports'].items():
                with urlopen('http://127.0.0.1:'+str(http.server_port)+url,timeout=10) as response:
                    self.assertIn('attachment',response.headers['Content-Disposition']);self.assertEqual(response.headers['X-Content-Type-Options'],'nosniff');bodies[fmt]=response.read()
            record=json.loads(bodies['json']);expected={k:v for k,v in data.items() if k!='exports'};self.assertEqual(record['data'],expected);self.assertEqual(record['revision'],service.REVISION)
            rows=list(csv.reader(io.StringIO(bodies['csv'].decode())));self.assertEqual(rows[0],['Point','X','Y','Z','SignedOffset']);self.assertEqual(len(rows),306)
            for i,row in enumerate(rows[1:]):self.assertEqual(list(map(float,row)),[i+1,*data['points'][i],data['signedOffsets'][i]])
            self.assertEqual(self.model.read_bytes(),before)
            # Saved links retain the original result after a later aircraft edit.
            self.v.SetParmValUpdate(self.cloud,'X_Rel_Location','XForm',7);self.v.WriteVSPFile(str(self.model),self.v.SET_ALL)
            for fmt,url in data['exports'].items():
                args=parse_qs(urlsplit(url).query);body,_,_=service.query_export(args['id'][0],fmt);self.assertEqual(body,bodies[fmt])
        finally:http.shutdown();http.server_close();thread.join()
    def test_missing_traversal_and_symlink_exports_reject(self):
        data=self.query();identifier=parse_qs(urlsplit(data['exports']['json']).query)['id'][0]
        for key,fmt in [('../outside','json'),('f'*32,'json'),(identifier,'request.json')]:
            with self.assertRaises(ValueError):service.query_export(key,fmt)
        folder=self.path/'queries'/identifier;(folder/'plane.csv').unlink();(folder/'plane.csv').symlink_to(self.model)
        with self.assertRaises(ValueError):service.query_export(identifier,'csv')
    def test_csv_preserves_extreme_finite_values_and_signed_zero(self):
        from unittest.mock import patch
        import math
        points=[[-0.0,5e-324,1.7976931348623157e308],[math.pi,1e-180,-1e-180]];offsets=[-0.0,-2.2250738585072014e-308]
        def native_result(request,model,folder):
            folder.mkdir(parents=True)
            return dict(engineVersion='serialization fixture',points=points,signedOffsets=offsets)
        with patch.object(service,'invoke',side_effect=native_result):data=self.query()
        identifier=parse_qs(urlsplit(data['exports']['csv']).query)['id'][0];body,_,_=service.query_export(identifier,'csv');rows=list(csv.reader(io.StringIO(body.decode())))
        for i,row in enumerate(rows[1:]):
            values=list(map(float,row[1:]));expected=[*points[i],offsets[i]];self.assertEqual(values,expected)
            for actual,original in zip(values,expected):self.assertEqual(math.copysign(1,actual),math.copysign(1,original))
