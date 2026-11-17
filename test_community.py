import tempfile
import unittest
from types import SimpleNamespace as NS
from community_bot import Store, Community, event_line
from community_editorial import before_start, result_for
from datetime import datetime, timezone


class Checks(unittest.TestCase):
    def test_posts_not_repeated_after_restart(self):
        with tempfile.TemporaryDirectory() as path:
            store = Store(path+'/test.db')
            self.assertFalse(store.enabled())
            post = store.draft('hello','slot')
            self.assertEqual(store.claim(post),'hello')
            self.assertIsNone(store.claim(post))
            store.db.close()
            store = Store(path+'/test.db')
            self.assertIsNone(store.draft('hello','slot'))
            self.assertIsNone(store.claim(post))
            store.db.close()

    def test_admin_boundaries(self):
        service = Community.__new__(Community)
        service.admins,service.group={123},-99
        update=NS(effective_user=NS(id=123,is_bot=False),effective_chat=NS(type='private',id=123),message=NS(sender_chat=None))
        self.assertTrue(service.allowed(update,True))
        update.effective_user.id=124
        self.assertFalse(service.allowed(update,True))
        update.effective_chat=NS(type='supergroup',id=-98)
        self.assertFalse(service.allowed(update))
        update.effective_chat.id=-99
        self.assertTrue(service.allowed(update))
        update.message.sender_chat=NS(id=123)
        self.assertFalse(service.allowed(update))

    def test_local_date_and_live_filter(self):
        event={'date':'2026-11-16T20:00:00Z','competitions':[{'status':{'type':{'state':'pre'}},'competitors':[{'homeAway':side,'team':{'displayName':side}} for side in ['home','away']]}]}
        self.assertIn('04:00',event_line(event,'英超','2026-11-17'))
        self.assertIsNone(event_line(event,'英超','2026-11-16'))
        self.assertIsNone(event_line(event,'英超','2026-11-17',True))
        self.assertIsNone(event_line({},'英超','2026-11-17'))

    def test_no_late_picks_or_unfinished_settlement(self):
        item = dict(state='pre',kickoff='2026-11-17T08:00:00Z',completed=False,
                    sport='soccer',detail='Full Time',home_score='2',away_score='1')
        self.assertTrue(before_start(item,datetime(2026,11,17,7,tzinfo=timezone.utc)))
        self.assertFalse(before_start(item,datetime(2026,11,17,8,tzinfo=timezone.utc)))
        self.assertIsNone(result_for(item))
        item.update(state='post',completed=True)
        self.assertEqual(result_for(item),'home')
        item['detail']='After Penalties'
        self.assertIsNone(result_for(item))
        item.update(sport='basketball',home_score='90',away_score='100')
        self.assertEqual(result_for(item),'away')


if __name__=='__main__':
    unittest.main()
