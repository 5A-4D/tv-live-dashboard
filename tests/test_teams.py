"""Phone signals are independent from the read-only TV API and contain no messages."""
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from test_data import api

class TeamsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.config_path, self.state_path = root/'config.json', root/'teams.json'
        self.config = {'token':'s'*48,'allowed_clients':['127.0.0.1'],
                       'setup_nonce':'one-use-setup-nonce','setup_expires_at':time.time()+60,
                       'receiver_url':'http://192.0.2.10:8770/teams'}
        self.save_config()
        self.patches = [patch.object(api,'TEAMS_CONFIG',self.config_path),
                        patch.object(api,'TEAMS_STATE',self.state_path),
                        patch.object(api,'FEED',root/'missing-feed')]
        for item in self.patches:item.start()
        self.server = api.ThreadingHTTPServer(('127.0.0.1',0),api.TeamsSignalHandler)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:'+str(self.server.server_address[1])

    def save_config(self):
        self.config_path.write_text(json.dumps(self.config))

    def tearDown(self):
        self.server.shutdown();self.server.server_close()
        for item in reversed(self.patches):item.stop()
        self.directory.cleanup()

    def post(self, payload, key=None, raw=False):
        data = payload if raw else json.dumps(payload).encode()
        request = Request(self.base+'/teams', data=data,
                          headers={'Authorization':'Bearer '+(key or self.config['token']),
                                   'Content-Type':'application/json'},method='POST')
        return json.load(urlopen(request,timeout=3))

    def assert_rejected(self, status, payload, **kwargs):
        with self.assertRaises(HTTPError) as raised:self.post(payload,**kwargs)
        self.assertEqual(raised.exception.code,status)

    def test_missing_state_is_awaiting_first_signal_not_zero_unread(self):
        state = api.teams_status()
        self.assertTrue(state['configured'])
        self.assertFalse(state['initialized'])
        self.assertFalse(state['pending'])

    def test_fixed_events_persist_and_clear_without_losing_last_receipt(self):
        self.assertEqual(self.post({'event':'received'}),{'ok':True})
        first = api.teams_status()
        self.assertTrue(first['pending'])
        self.assertTrue(first['initialized'])
        # State can be loaded by a fresh process without any in-memory notification cache.
        saved = json.loads(self.state_path.read_text())
        self.assertEqual(set(saved),{'schema','last_event_at','last_received_at','pending'})
        self.assertEqual(self.state_path.stat().st_mode & 0o777,0o600)
        self.post({'event':'clear'})
        cleared = api.teams_status()
        self.assertFalse(cleared['pending'])
        self.assertEqual(cleared['last_received_at'],first['last_received_at'])
        self.post({'event':'received'})
        self.assertGreater(api.teams_status()['last_received_at'],first['last_received_at'])

    def test_message_contents_and_invalid_payloads_are_rejected_without_storage(self):
        for payload in ({'event':'received','message':'PRIVATE MESSAGE'}, {'event':'PRIVATE MESSAGE'},
                        {'event':{'message':'PRIVATE MESSAGE'}}, [], {'notification':'PRIVATE MESSAGE'}):
            self.assert_rejected(400,payload)
        self.assert_rejected(400,b'{invalid json',raw=True)
        self.assert_rejected(413,b'x'*129,raw=True)
        self.assertFalse(self.state_path.exists())

    def test_source_and_separate_key_are_both_required(self):
        self.assert_rejected(403,{'event':'received'},key='TV-read-key')
        self.assert_rejected(403,{'event':'received'},key='é'*48)
        self.config['allowed_clients']=['192.0.2.30'];self.save_config()
        self.assert_rejected(403,{'event':'received'})
        self.assertFalse(self.state_path.exists())

    def test_pasted_authorization_tolerates_case_and_spaces_but_still_requires_exact_key(self):
        for header, expected_code, expected_error in (
            ('',403,'Authorization header missing'),
            (self.config['token'],403,'Authorization header format incorrect'),
            ('Bearer wrong-key',403,'Receiver key does not match'),
            ('  bearer   '+self.config['token']+'  ',200,None),
        ):
            # Invalid event probes auth without generating a notification signal.
            request=Request(self.base+'/teams',data=b'{"event":"probe"}',
                            headers={'Authorization':header,'Content-Type':'application/json'},method='POST')
            with self.assertRaises(HTTPError) as error:urlopen(request)
            self.assertEqual(error.exception.code,400 if expected_code==200 else expected_code)
            body=json.load(error.exception)
            if expected_error:self.assertEqual(body['error'],expected_error)
            self.assertNotIn(self.config['token'],json.dumps(body))
        self.assertFalse(self.state_path.exists())

    def test_signal_key_cannot_read_dashboard_and_read_key_cannot_send_signal(self):
        reader = api.ThreadingHTTPServer(('127.0.0.1',0),api.Handler)
        reader.token='r'*48
        thread=threading.Thread(target=reader.serve_forever,daemon=True);thread.start()
        try:
            with patch.object(api,'ALLOWED_CLIENTS',frozenset({'127.0.0.1'})):
                request=Request('http://127.0.0.1:'+str(reader.server_address[1])+'/api/dashboard',
                                headers={'Authorization':'Bearer '+self.config['token']})
                with self.assertRaises(HTTPError) as error:urlopen(request)
                self.assertEqual(error.exception.code,403)
                self.assert_rejected(403,{'event':'received'},key=reader.token)
            with self.assertRaises(HTTPError) as error:urlopen(self.base+'/api/dashboard')
            self.assertEqual(error.exception.code,404)
            self.assertNotIn(self.config['token'],json.dumps(api.dashboard()))
            self.assertNotIn('setup_nonce',json.dumps(api.dashboard()))
        finally:
            reader.shutdown();reader.server_close()

    def test_setup_page_is_source_restricted_expires_and_is_not_cached(self):
        url=self.base+'/setup/'+self.config['setup_nonce']
        with urlopen(url) as response:
            self.assertEqual(response.headers['Cache-Control'],'no-store')
            self.assertIn(self.config['token'],response.read().decode())
        self.config['setup_expires_at']=time.time()-1;self.save_config()
        with self.assertRaises(HTTPError) as error:urlopen(url)
        self.assertEqual(error.exception.code,404)
        self.config['allowed_clients']=['192.0.2.30'];self.save_config()
        with self.assertRaises(HTTPError) as error:urlopen(url)
        self.assertEqual(error.exception.code,403)

if __name__ == '__main__':
    unittest.main()
