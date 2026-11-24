"""HTTP boundary checks use a fake research call; no paid model requests."""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import serve


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.trace = '20261119-000000-' + 'a' * 32 + '.json'
        path = self.root / 'results/search_agent/v4/traces' / self.trace
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'snapshot':{'is_live':False},'steps':[
            {'action':{'tool':'find_players','arguments':{}},
             'observation':{'players':[]},'stdout':'private runtime details'}]}))
        self.patcher = patch.object(serve, 'ROOT', self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.search = Mock(return_value={'answer':'Saved result','trace':self.trace})
        self.server = ThreadingHTTPServer(('127.0.0.1',0), BaseHTTPRequestHandler)
        self.port = self.server.server_port
        self.server.RequestHandlerClass = serve.make_handler({'last_completed_gameweek':38}, self.port, self.search)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, body=None, origin=True):
        connection = http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        headers = {'Content-Type':'application/json'}
        if origin:
            headers['Origin'] = f'http://127.0.0.1:{self.port}'
        connection.request(method,path,body,headers)
        response = connection.getresponse()
        content = response.read()
        status = response.status
        connection.close()
        return status, content

    def test_snapshot_and_active_page(self):
        status, body = self.request('GET','/api/snapshot')
        self.assertEqual((status,json.loads(body)['last_completed_gameweek']),(200,38))
        status, body = self.request('GET','/')
        self.assertEqual(status,200)
        self.assertIn(b'research-form',body)
        self.assertNotIn(b'id="pitch"',body)
        self.assertEqual(self.request('GET','/api/demo')[0],404)

    def test_valid_search_returns_safe_evidence(self):
        status, body = self.request('POST','/api/search',json.dumps({'question':'Find players'}))
        value = json.loads(body)
        self.assertEqual((status,value['answer']),(200,'Saved result'))
        self.assertEqual(value['evidence']['steps'][0]['action']['tool'],'find_players')
        self.assertNotIn('private runtime details',body.decode())
        self.search.assert_called_once_with('Find players')

    def test_invalid_input_and_cross_origin_never_call_model(self):
        self.assertEqual(self.request('POST','/api/search','{}')[0],400)
        self.assertEqual(self.request('POST','/api/search','{broken')[0],400)
        self.assertEqual(self.request('POST','/api/search','{"question":"x"}',False)[0],403)
        self.search.assert_not_called()

    def test_model_failure_is_an_error_response(self):
        self.search.side_effect = RuntimeError('Research request failed')
        status, body = self.request('POST','/api/search','{"question":"x"}')
        self.assertEqual(status,502)
        self.assertEqual(json.loads(body)['error'],'Research request failed')

    def test_evidence_filename_cannot_escape_trace_directory(self):
        with self.assertRaises(ValueError):
            serve.evidence_for('../../private.json')


if __name__ == '__main__':
    unittest.main()
