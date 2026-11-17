"""Original editorial previews and immutable, paper-only prediction records."""
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone

from espn_api import get_scoreboard


def fixture(event, sport, league, label):
    try:
        comp = event['competitions'][0]
        teams = {t['homeAway']: t for t in comp['competitors']}
        return dict(id=str(event['id']), sport=sport, league=league, label=label,
                    kickoff=event['date'], state=comp['status']['type']['state'],
                    completed=comp['status']['type'].get('completed', False),
                    detail=comp['status']['type'].get('detail', ''),
                    home=teams['home']['team']['displayName'],
                    away=teams['away']['team']['displayName'],
                    home_records=teams['home'].get('records', []),
                    away_records=teams['away'].get('records', []),
                    home_form=teams['home'].get('form', ''),
                    away_form=teams['away'].get('form', ''),
                    home_score=teams['home'].get('score'), away_score=teams['away'].get('score'),
                    source='ESPN')
    except (KeyError, IndexError, TypeError):
        return None


def before_start(item, now=None):
    return item['state'] == 'pre' and datetime.fromisoformat(item['kickoff'].replace('Z', '+00:00')) > (now or datetime.now(timezone.utc))


def result_for(item):
    if not item['completed'] or item['state'] != 'post':
        return None
    # Football 1X2 is regulation time. Do not settle extra time / penalties as 90 minutes.
    if item['sport'] == 'soccer' and item['detail'].lower() not in {'full time', 'ft'}:
        return None
    try:
        h, a = int(item['home_score']), int(item['away_score'])
    except (TypeError, ValueError):
        return None
    return 'home' if h > a else 'away' if a > h else 'draw'


class Editorial:
    def __init__(self, service, leagues, tz):
        self.service, self.leagues, self.tz = service, leagues, tz
        self.db = service.store.db
        self.db.execute('CREATE TABLE IF NOT EXISTS picks (post_id INTEGER PRIMARY KEY, event_id TEXT UNIQUE, snapshot TEXT NOT NULL, choice TEXT NOT NULL, created TEXT NOT NULL, result TEXT)')
        self.db.commit()

    async def upcoming(self):
        now = datetime.now(timezone.utc)
        dates = [(now+timedelta(days=d)).strftime('%Y%m%d') for d in range(3)]
        calls = [(s,l,n,d) for s,l,n in self.leagues for d in dates]
        data = await asyncio.gather(*[asyncio.to_thread(get_scoreboard,s,l,d) for s,l,n,d in calls])
        items = {}
        for (s,l,n,d), board in zip(calls,data):
            for event in board.get('events', []):
                item = fixture(event,s,l,n)
                if item and before_start(item,now) and datetime.fromisoformat(item['kickoff'].replace('Z','+00:00')) < now+timedelta(hours=48):
                    item['scoreboard_date'] = d
                    items[item['id']] = item
        return sorted(items.values(), key=lambda x:x['kickoff'])

    async def fresh(self, item):
        date = item.get('scoreboard_date') or datetime.fromisoformat(item['kickoff'].replace('Z','+00:00')).strftime('%Y%m%d')
        data = await asyncio.to_thread(get_scoreboard,item['sport'],item['league'],date)
        for event in data.get('events', []):
            if str(event['id']) == item['id']:
                return fixture(event,item['sport'],item['league'],item['label'])
        return None

    async def focus(self):
        items = (await self.upcoming())[:12]
        lines = ['LA1｜未來 48 小時賽事候選', '依支援聯賽與開賽時間排列；並非投注熱度排行。']
        for item in items:
            when = datetime.fromisoformat(item['kickoff'].replace('Z','+00:00')).astimezone(self.tz)
            lines.append(f"{item['id']}｜{when:%m/%d %H:%M} {item['label']}\n{item['home']} vs {item['away']}")
        if not items:
            lines.append('目前未取得未開賽資料，稍後再查。')
        lines.append('管理員：/pick 賽事編號 產生模擬注單預覽。時間 UTC+8；資料 ESPN。')
        return '\n\n'.join(lines)

    async def pick(self, event_id):
        previous = self.db.execute('SELECT post_id FROM picks WHERE event_id=?',(event_id,)).fetchone()
        if previous:
            return f'此場已保留預測 #{previous[0]}，不重抽或覆寫；可用 /review 查看結果。'
        item = next((x for x in await self.upcoming() if x['id']==event_id),None)
        if not item:
            return '此場未取得或已開賽；請用 /focus 選擇未開賽賽事。'
        async with self.service.ai_limit:
            response = await self.service.ai.chat.completions.create(
                model=os.environ.get('OPENAI_MODEL','gpt-4.1-mini'),
                response_format={'type':'json_object'}, max_completion_tokens=800, store=False,
                messages=[{'role':'system','content':
                    '你是 LA1 體育編輯。僅根據附上賽事資料提出賽前觀點，繁體中文帶自然香港語氣。'
                    '輸出 JSON：choice=home/away/draw/pass，reason=不超過160字的數據理由，risk=不超過100字的風險。'
                    '資料不足選 pass；籃球棒球不能選 draw。不得捏造近期戰績、傷停、賠率、勝率或保證獲利。'
                    '這是未經驗證的模擬預測，不是實際下注。'},
                    {'role':'user','content':json.dumps(item,ensure_ascii=False)}])
        choice = response.choices[0]
        if choice.finish_reason != 'stop':
            return '預覽未完成，尚未建立紀錄，請稍後再試。'
        answer = json.loads(choice.message.content)
        side = answer.get('choice')
        if side not in {'home','away','draw','pass'} or (side=='draw' and item['sport']!='soccer'):
            return '預測格式不完整，尚未建立紀錄。'
        if not all(isinstance(answer.get(k),str) and answer[k].strip() for k in ['reason','risk']):
            return '預測理由不完整，尚未建立紀錄。'
        current = await self.fresh(item)
        if not current or not before_start(current):
            return '賽事狀態已變更或無法確認，未建立預測。'
        when = datetime.fromisoformat(item['kickoff'].replace('Z','+00:00')).astimezone(self.tz)
        created = datetime.now(timezone.utc)
        direction = {'home':item['home']+' 勝','away':item['away']+' 勝','draw':'和局','pass':'觀望（資料不足）'}[side]
        text = (f"LA1｜賽前模擬注單\n{item['label']}｜{when:%m/%d %H:%M}（UTC+8）\n"
                f"{item['home']} vs {item['away']}\n方向：{direction}\n"
                f"模擬單位：{'0' if side=='pass' else '1'}｜未實際下注\n\n"
                f"觀點：{answer['reason'][:250]}\n風險：{answer['risk'][:180]}\n\n"
                f"賠率未接入，不計算收益。{'足球只核對90分鐘賽果。' if item['sport']=='soccer' else '按最終賽果核對（含延長）。'}\n"
                f"來源：ESPN｜紀錄：{created.astimezone(self.tz):%Y/%m/%d %H:%M}\n"
                'GPT 觀點尚未驗證預測優勢；結果不保證。你覺得今場關鍵在哪？')
        # One immutable snapshot per event, committed together with the preview.
        with self.db:
            post_id = self.db.execute('INSERT INTO posts(text) VALUES (?)',(text,)).lastrowid
            self.db.execute('INSERT INTO picks VALUES (?,?,?,?,?,NULL)',
                            (post_id,event_id,json.dumps(item,ensure_ascii=False),side,created.isoformat()))
        return f'預覽 #{post_id}（尚未發布；賽前紀錄已保存）\n\n{text}\n\n發布：/publish {post_id}'

    async def can_publish(self, post_id):
        row = self.db.execute('SELECT snapshot FROM picks WHERE post_id=?',(post_id,)).fetchone()
        if not row:
            return True
        item = await self.fresh(json.loads(row[0]))
        return bool(item and before_start(item))

    async def review(self):
        rows = self.db.execute('SELECT post_id,snapshot,choice FROM picks WHERE result IS NULL').fetchall()
        for post_id, raw, side in rows:
            item = await self.fresh(json.loads(raw))
            outcome = result_for(item) if item else None
            if outcome:
                with self.db:
                    self.db.execute('UPDATE picks SET result=? WHERE post_id=? AND result IS NULL',
                                    (json.dumps({'side':outcome,'home':item['home_score'],'away':item['away_score'] }),post_id))
        rows = self.db.execute('SELECT p.post_id,p.snapshot,p.choice,p.result,s.status FROM picks p JOIN posts s ON s.id=p.post_id ORDER BY p.post_id DESC').fetchall()
        settled = [r for r in rows if r[3] and r[2]!='pass']
        hits = sum(json.loads(r[3])['side']==r[2] for r in settled)
        lines = [f'LA1｜完整模擬復盤\n累計 {len(rows)} 場｜已核對 {len(settled)} 場｜符合 {hits}、失準 {len(settled)-hits}',
                 '包含未發布預覽；非實際投注戰績。沒有賠率，不計損益。']
        for post_id, raw, side, result, status in rows[:15]:
            item = json.loads(raw)
            if result:
                result = json.loads(result)
                label = '觀望' if side=='pass' else '符合' if side==result['side'] else '失準'
                label += f"｜{result['home']}:{result['away']}"
            else:
                label = '待完場／待資料確認'
            lines.append(f"#{post_id} {item['home']} vs {item['away']}\n{label}｜{'已發布' if status=='sent' else '未確認發布'}")
        return '\n\n'.join(lines)
