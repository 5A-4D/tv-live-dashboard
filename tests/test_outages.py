import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('outage_api',Path(__file__).resolve().parents[1]/'server/server.py')
api=importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)

class OutageTests(unittest.TestCase):
    def test_microsoft_active_report_and_operational_status(self):
        payload={'Status':'Service degradation','Title':'Users cannot connect to <b>Outlook</b>',
                 'LastUpdatedTime':'2026-11-12T22:11:39+00:00','Message':'Unselected content'}
        items=api.select_outages('Microsoft 365','microsoft',payload,'https://status.cloud.microsoft/',1000)
        self.assertEqual(items[0]['title'],'Users cannot connect to Outlook')
        self.assertEqual(items[0]['checked_at'],1000)
        self.assertEqual(items[0]['url'],'https://status.cloud.microsoft/')
        self.assertIsInstance(items[0]['updated_at'],float)
        self.assertNotIn('Message',items[0])
        self.assertEqual(api.select_outages('Microsoft 365','microsoft',{'Status':'Available'},'https://status.cloud.microsoft/',1000),[])
        with self.assertRaises(ValueError):
            api.select_outages('Microsoft 365','microsoft',{'Status':'Unrecognized'},'https://status.cloud.microsoft/',1000)
        with self.assertRaises(ValueError):
            api.select_outages('Microsoft 365','microsoft',{'Status':'Service degradation'},'https://status.cloud.microsoft/',1000)

    def test_statuspage_excludes_resolved_and_restricts_source_links(self):
        payload={'incidents':[
            {'name':'API failure','status':'identified','impact':'major','updated_at':'2026-11-12T22:11:39Z','shortlink':'https://unrelated.example/'},
            {'name':'Recovered','status':'resolved','impact':'critical'},
            {'name':'Planned work','status':'scheduled','impact':'minor'}]}
        items=api.select_outages('Discord','statuspage',payload,'https://discordstatus.com/',1000)
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['severity'],'critical')
        self.assertEqual(items[0]['url'],'https://discordstatus.com/')
        with self.assertRaises(ValueError):
            api.select_outages('Discord','statuspage',{},'https://discordstatus.com/',1000)

    def test_status_rss_requires_explicit_active_state_and_ignores_resolved_history(self):
        payload=b'''<rss><channel>
          <item><title>Current errors</title><description>&lt;b&gt;Status: Investigating&lt;/b&gt;&lt;br/&gt;Working on recovery.</description><pubDate>Thu, 12 Nov 2026 18:29:14 GMT</pubDate><link>https://status.openai.com/incidents/example</link></item>
          <item><title>Past errors</title><description>&lt;b&gt;Status: Resolved&lt;/b&gt; Previously investigating.</description></item>
        </channel></rss>'''
        items=api.select_outages('OpenAI','rss',payload,'https://status.openai.com/',1000)
        self.assertEqual([item['title'] for item in items],['Current errors'])
        self.assertEqual(items[0]['status'],'Investigating')
        self.assertIsNotNone(items[0]['updated_at'])
        with self.assertRaises(ValueError):
            api.select_outages('OpenAI','rss',b'<html/>','https://status.openai.com/',1000)
        with self.assertRaises(ValueError):
            api.select_outages('OpenAI','rss',b'<rss><channel><item><description>Investigating earlier errors.</description></item></channel></rss>','https://status.openai.com/',1000)

    def test_failed_refresh_keeps_original_age_reports_failure_and_expires_old_reports(self):
        source=('Microsoft 365','https://status.cloud.microsoft/api/posts/mac','microsoft','https://status.cloud.microsoft/')
        item={'source':'Microsoft 365','title':'Service incident','checked_at':900}
        previous={'Microsoft 365':[item]}
        state={}
        with patch.object(api,'OUTAGE_SOURCES',(source,)),patch.object(api,'OUTAGES',state),patch.object(api,'fetch_outages',side_effect=TimeoutError),patch.object(api.time,'time',return_value=1000):
            current=api.refresh_outages(previous)
            self.assertEqual(current,previous)
            self.assertEqual(state['items'],[item])
            self.assertEqual(state['unavailable_sources'],['Microsoft 365'])
            self.assertEqual(state['items'][0]['checked_at'],900)
            with patch.object(api.time,'time',return_value=4500):
                api.refresh_outages(current)
            self.assertEqual(state['items'],[])
            self.assertEqual(state['unavailable_sources'],['Microsoft 365'])

    def test_successful_recovery_removes_saved_incidents(self):
        source=('Discord','https://discordstatus.com/api/v2/incidents/unresolved.json','statuspage','https://discordstatus.com/')
        state={}
        with patch.object(api,'OUTAGE_SOURCES',(source,)),patch.object(api,'OUTAGES',state),patch.object(api,'fetch_outages',return_value=[]):
            current=api.refresh_outages({'Discord':[{'source':'Discord','title':'Old incident','checked_at':1000}]})
        self.assertEqual(current,{'Discord':[]})
        self.assertEqual(state['items'],[])
        self.assertEqual(state['unavailable_sources'],[])

if __name__=='__main__':
    unittest.main()
