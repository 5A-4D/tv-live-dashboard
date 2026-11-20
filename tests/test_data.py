import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from datetime import date,datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

collector = module('collector', 'scripts/collect_feed.py')
api = module('api', 'server/server.py')
work = module('work', 'scripts/collect_work.py')
codex = module('codex', 'scripts/collect_codex.py')

class DataTests(unittest.TestCase):
    def test_reminders_preserve_verbatim_source_and_stable_priority(self):
        raw = '# My reminders\n- [x] 1. Finished\n- [ ] 3. Later\n- [ ] 1. First\n- [ ] 1. Also first\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'reminder.txt'
            path.write_text(raw)
            result = collector.reminders(path)
            self.assertEqual(result['raw'], raw)
            self.assertEqual(path.read_text(), raw)
            self.assertEqual([item['text'] for item in result['items']], ['1. First', '1. Also first', '3. Later', '1. Finished'])
            self.assertEqual(result['unfinished'], 3)
            self.assertEqual(result['completed'], 1)

    def test_old_reports_cannot_claim_online_services(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'container-status.json').write_text(json.dumps({'checked_at': 100, 'docker_ok': True, 'containers': [{'name':'jellyfin','state':'running','health':'healthy'}]}))
            (root/'jarvis-heartbeat.json').write_text(json.dumps({'timestamp':100,'ready':True}))
            with patch.object(collector,'BOT_DATA',root), patch.object(collector,'REMINDERS',root/'missing'):
                result = collector.collect(now=1000)
            self.assertTrue(all(not service['online'] and service['stale'] for service in result['services']))
            self.assertFalse(result['jarvis']['ready'])

    def test_api_auth_source_gate_and_read_only_behavior(self):
        server = api.ThreadingHTTPServer(('127.0.0.1', 0), api.Handler)
        server.token = 'a' * 48
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        base = 'http://127.0.0.1:' + str(server.server_address[1])
        try:
            with patch.object(api,'ALLOWED_CLIENTS',frozenset({'127.0.0.1'})), patch.object(api,'dashboard',return_value={'schema':1}):
                self.assertEqual(json.load(urlopen(base+'/healthz')), {'ok':True})
                with self.assertRaises(HTTPError) as error:
                    urlopen(base+'/api/dashboard')
                self.assertEqual(error.exception.code,403)
                request = Request(base+'/api/dashboard',headers={'Authorization':'Bearer '+server.token})
                self.assertEqual(json.load(urlopen(request)),{'schema':1})
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base+'/api/dashboard',method='POST',data=b'{}'))
                self.assertEqual(error.exception.code,405)
            with patch.object(api,'ALLOWED_CLIENTS',frozenset({'192.0.2.20'})):
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base+'/api/dashboard',headers={'Authorization':'Bearer '+server.token}))
                self.assertEqual(error.exception.code,403)
        finally:
            server.shutdown()
            server.server_close()

    def test_failed_collector_is_marked_stale(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(api,'FEED',Path(directory)/'missing'):
            self.assertTrue(api.dashboard()['feed_stale'])

    def test_calendar_output_contains_only_clipped_anonymous_intervals(self):
        zone=ZoneInfo('America/Chicago')
        availability=SimpleNamespace(meetings=(
            SimpleNamespace(start=datetime(2026,11,4,8,0,tzinfo=zone),end=datetime(2026,11,4,9,0,tzinfo=zone)),
            SimpleNamespace(start=datetime(2026,11,4,8,45,tzinfo=zone),end=datetime(2026,11,4,10,0,tzinfo=zone)),
        ),all_day=())
        days=work.anonymous_days(availability,date(2026,11,4),zone,'08:30','16:00')
        self.assertEqual(set(days[0]),{'date','working','start','end','busy'})
        self.assertEqual(days[0]['busy'],[{'start':datetime(2026,11,4,8,30,tzinfo=zone).timestamp(),'end':datetime(2026,11,4,10,0,tzinfo=zone).timestamp()}])
        self.assertFalse(days[3]['working'])

    def test_work_refresh_keeps_anonymous_schedule_on_failure_and_recovers(self):
        zone=ZoneInfo('America/Chicago')
        saved={'available':True,'checked_at':1000,'timezone':str(zone),
               'days':work.anonymous_days(SimpleNamespace(meetings=(),all_day=()),date(2026,11,12),zone,'08:30','16:00')}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'work.json'
            with patch.object(work,'collect',AsyncMock(return_value=saved)):
                self.assertEqual(work.refresh(path),saved)
            self.assertEqual(json.loads(path.with_name('work-last-good.json').read_text()),saved)
            with patch.object(work,'collect',AsyncMock(side_effect=TimeoutError('PRIVATE ERROR CONTENT'))):
                for _ in range(2):
                    result=work.refresh(path)
                    self.assertEqual(result,{**saved,'refresh_failed':True})
                    self.assertNotIn('PRIVATE',path.read_text())
                    self.assertEqual(json.loads(path.with_name('work-last-good.json').read_text()),saved)
            new={**saved,'checked_at':2000}
            with patch.object(work,'collect',AsyncMock(return_value=new)):
                self.assertEqual(work.refresh(path),new)
            self.assertNotIn('refresh_failed',json.loads(path.read_text()))
            self.assertEqual(json.loads(path.with_name('work-last-good.json').read_text()),new)

    def test_work_refresh_cold_failure_and_corrupt_cache_do_not_invent_availability(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'work.json'
            path.with_name('work-last-good.json').write_text('{invalid')
            with patch.object(work,'collect',AsyncMock(side_effect=TimeoutError)):
                result=work.refresh(path)
            self.assertFalse(result['available'])
            self.assertIsNone(result['checked_at'])
            self.assertEqual(result['days'],[])

    def test_work_cache_migration_strips_extra_fields_and_preserves_timestamp(self):
        zone=ZoneInfo('America/Chicago')
        days=work.anonymous_days(SimpleNamespace(meetings=(),all_day=()),date(2026,11,12),zone,'08:30','16:00')
        saved={'available':True,'checked_at':1000,'timezone':str(zone),'days':days}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'work.json'
            path.write_text(json.dumps({**saved,'unexpected':'PRIVATE'}))
            with patch.object(work,'collect',AsyncMock(side_effect=TimeoutError)):
                result=work.refresh(path)
            self.assertEqual(result,{**saved,'refresh_failed':True})
            self.assertNotIn('PRIVATE',path.read_text())
            days[0]['busy'][0]['end']=days[0]['end']+1
            path.write_text(json.dumps(saved))
            self.assertIsNone(work.saved_work(path))

    def test_failed_work_refresh_raises_alert_even_with_recent_saved_data(self):
        source={'feed_stale':False,'services':[{'id':'jellyfin','online':True,'stale':False}],
                'work':{'available':True,'checked_at':990,'refresh_failed':True},
                'codex':{'available':True,'checked_at':990,'windows':[]},
                'weather':{'available':True,'checked_at':990}}
        self.assertEqual([a['id'] for a in api.useful_alerts(source,1000)],['work-stale'])

    def test_codex_selection_does_not_export_account_or_auth_fields(self):
        result={'private_account':'do-not-export','rateLimitsByLimitId':{'codex':{'primary':{'usedPercent':23,'windowDurationMins':300,'resetsAt':1234,'private':'do-not-export'}}}}
        self.assertEqual(codex.select_limits(result),[{'used_percent':23,'window_minutes':300,'resets_at':1234}])

    def test_dashboard_morning_hour_blocks_weekdays_and_merges_overlapping_meetings(self):
        zone=ZoneInfo('America/Chicago')
        stamp=lambda day,hour,minute:datetime(2026,11,day,hour,minute,tzinfo=zone)
        availability=SimpleNamespace(meetings=(
            SimpleNamespace(start=stamp(9,9,15),end=stamp(9,10,0)),
            SimpleNamespace(start=stamp(9,12,45),end=stamp(9,13,0)),
        ),all_day=())
        days=work.anonymous_days(availability,date(2026,11,9),zone,'08:30','16:00')
        self.assertEqual(days[0]['busy'],[
            {'start':stamp(9,8,30).timestamp(),'end':stamp(9,10,0).timestamp()},
            {'start':stamp(9,12,45).timestamp(),'end':stamp(9,13,0).timestamp()},
        ])
        self.assertEqual(days[1]['busy'],[{'start':stamp(10,8,30).timestamp(),'end':stamp(10,9,30).timestamp()}])
        self.assertTrue(all(not day['busy'] and not day['working'] for day in days[5:]))

    def test_dashboard_morning_block_uses_configured_start_and_stays_within_short_day(self):
        zone=ZoneInfo('America/Chicago')
        days=work.anonymous_days(SimpleNamespace(meetings=(),all_day=()),date(2026,11,9),zone,'10:00','10:30')
        self.assertEqual(days[0]['busy'],[{'start':days[0]['start'],'end':days[0]['end']}])

    def test_activity_exports_only_state_and_times_and_ignores_previous_process_tasks(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(collector, 'BOT_DATA', Path(directory)):
            root = Path(directory)
            stamp = lambda value: datetime.fromtimestamp(value, ZoneInfo('UTC')).isoformat()
            (root/'live-progress.json').write_text(json.dumps({'active':[
                {'started_at':stamp(100),'events':['PRIVATE TASK CONTENT']},
                {'started_at':stamp(950),'request_id':'PRIVATE IDENTIFIER'}]}))
            records = [{'outcome':'success','completed_at':stamp(800),'conversation_id':'PRIVATE'},
                       {'outcome':'error','completed_at':stamp(990),'events':['PRIVATE']}]
            (root/'request-telemetry.jsonl').write_text('\n'.join(json.dumps(row) for row in records))
            result = collector.activity(True, 1000, process_started=900)
            self.assertEqual(result, {'state':'working','active_count':1,'started_at':950,'last_success_at':800})
            self.assertNotIn('PRIVATE', json.dumps(result))
            self.assertEqual(collector.activity(False,1000,900)['state'], 'offline')
            # An idle file need not change while Jarvis has no requests.
            (root/'live-progress.json').write_text(json.dumps({'active':[],'generated_at':stamp(1)}))
            self.assertEqual(collector.activity(True,1000,900)['state'], 'idle')

    def test_weather_rejects_wrong_units_and_stale_conditions(self):
        source = {'current_units':{'temperature_2m':'°F'},
                  'current':{'time':990,'temperature_2m':68,'apparent_temperature':65,'weather_code':3,'wind_speed_10m':10},
                  'daily':{'temperature_2m_max':[72],'temperature_2m_min':[45],'precipitation_probability_max':[25]},
                  'private':'not exported'}
        selected = api.select_weather(source,1000)
        self.assertEqual((selected['temperature'],selected['high'],selected['rain_chance'],selected['unit']),(68,72,25,'°F'))
        self.assertNotIn('private',selected)
        with self.assertRaises(ValueError):api.select_weather(source,5000)
        source['current_units']['temperature_2m']='°C'
        with self.assertRaises(ValueError):api.select_weather(source,1000)

    def test_alerts_do_not_treat_stale_health_or_expired_limits_as_current(self):
        source={'feed_stale':False,'services':[{'id':'jellyfin','label':'Jellyfin','stale':True,'online':False}],
                'host':{'storage':[{'label':'System','used_percent':95}]},
                'work':{'available':True,'checked_at':990},'weather':{'available':True,'checked_at':990},
                'codex':{'available':True,'checked_at':990,'windows':[{'used_percent':100,'window_minutes':300,'resets_at':900}]}}
        alerts=api.useful_alerts(source,1000)
        self.assertEqual({a['id'] for a in alerts},{'services-stale','storage-System'})
        source['codex']['windows'][0]['resets_at']=1100
        source['services'][0]['stale']=False
        alerts=api.useful_alerts(source,1000)
        self.assertEqual({a['id'] for a in alerts},{'jellyfin','storage-System','codex-5h'})
        source['feed_stale']=True
        self.assertEqual([a['id'] for a in api.useful_alerts(source,1000)],['feed'])

if __name__ == '__main__':
    unittest.main()
