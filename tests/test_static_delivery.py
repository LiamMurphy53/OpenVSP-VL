"""Cold editor imports must survive a simultaneous burst of module requests."""
import concurrent.futures,threading,unittest
from urllib.request import urlopen
import server

class StaticDelivery(unittest.TestCase):
    def test_simultaneous_modules_and_styles_match_current_source(self):
        class Quiet(server.Handler):
            def log_message(self,*args):pass
        http=server.StudioHTTPServer(('127.0.0.1',0),Quiet)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        files=list((server.ROOT/'web').glob('*.js'))[:48];self.assertEqual(len(files),48)
        barrier=threading.Barrier(len(files))
        def read(file):
            barrier.wait(timeout=10)
            with urlopen('http://127.0.0.1:'+str(http.server_port)+'/'+file.name+'?cold-start-check',timeout=2) as response:
                self.assertEqual(response.read(),file.read_bytes());self.assertIn('no-store',response.headers['Cache-Control'])
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(files)) as pool:list(pool.map(read,files))
            for file in ['index.html','style.css','workspace-layout.css']:
                with urlopen('http://127.0.0.1:'+str(http.server_port)+'/'+file,timeout=2) as response:self.assertEqual(response.read(),(server.ROOT/'web'/file).read_bytes())
        finally:http.shutdown();http.server_close();thread.join()
