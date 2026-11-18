import asyncio
import json
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta, timezone
from community_bot import Community, Store
from community_daily import caption, VERSION
from community_cover import daily_cover


def sample():
    start=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    return dict(format=VERSION,sport='basketball',date='2026-11-19',question='你最睇好邊場？',fixtures=[dict(id=str(i),state='pre',kickoff=start,local_start='11/19 08:00',home='Home',away='Away',home_zh='騎士',away_zh='灰熊',choice='home',reason='戰績較佳，仍須留意臨場輪替。',label='NBA') for i in range(5)])

class DailyChecks(unittest.IsolatedAsyncioTestCase):
    async def test_one_photo_full_caption_no_text_fallback(self):
        with tempfile.TemporaryDirectory() as path:
            service=Community.__new__(Community)
            service.store=Store(path+'/test.db')
            service.channel='test'
            post=sample()
            service.editorial=NS(fresh=AsyncMock(side_effect=lambda item:item))
            bot=NS(send_photo=AsyncMock(return_value=NS(chat_id=-123,message_id=4)),send_message=AsyncMock())
            raw=json.dumps(post,ensure_ascii=False)
            pid=service.store.draft(raw)
            service.store.claim(pid)
            await service.send_post(bot,pid,raw)
            bot.send_photo.assert_awaited_once()
            bot.send_message.assert_not_awaited()
            self.assertEqual(bot.send_photo.call_args.kwargs['caption'],caption(post))
            self.assertEqual(service.store.db.execute('SELECT message_id FROM deliveries').fetchone()[0],4)
            # Timeout cannot create a text-only post or duplicate retry.
            pid=service.store.draft(raw)
            service.store.claim(pid)
            bot.send_photo.side_effect=TimeoutError
            with self.assertRaises(TimeoutError):
                await service.send_post(bot,pid,raw)
            bot.send_message.assert_not_awaited()
            self.assertEqual(service.store.db.execute('SELECT status FROM posts WHERE id=?',(pid,)).fetchone()[0],'unknown')
            self.assertIsNone(service.store.claim(pid))
            service.store.db.close()

    async def test_started_fixture_not_published(self):
        with tempfile.TemporaryDirectory() as path:
            service=Community.__new__(Community);service.store=Store(path+'/test.db');service.channel='test'
            post=sample(); post['fixtures'][0]['state']='in'
            service.editorial=NS(fresh=AsyncMock(side_effect=lambda item:item))
            bot=NS(send_photo=AsyncMock(),send_message=AsyncMock())
            raw=json.dumps(post);pid=service.store.draft(raw)
            with self.assertRaises(ValueError):await service.send_post(bot,pid,raw)
            bot.send_photo.assert_not_awaited();bot.send_message.assert_not_awaited()
            service.store.db.close()

    def test_cover_and_caption_budget(self):
        from PIL import Image
        post=sample()
        self.assertLessEqual(len(caption(post).encode('utf-16-le'))//2,1000)
        self.assertEqual(Image.open(daily_cover(post)).size,(1080,1350))
        for row in post['fixtures']:row['reason']='過長'*500
        with self.assertRaises(ValueError):caption(post)

if __name__=='__main__':unittest.main()
