"""
隊名搜尋引擎 - 支援中文、英文、縮寫搜尋 + 運動類型關鍵字
"""

import re

# 運動類型關鍵字 → 對應的 ESPN sport 類別
SPORT_KEYWORDS = {
    "足球": "soccer",
    "英超": "soccer",
    "西甲": "soccer",
    "德甲": "soccer",
    "意甲": "soccer",
    "法甲": "soccer",
    "歐冠": "soccer",
    "歐霸": "soccer",
    "soccer": "soccer",
    "football": "soccer",
    "棒球": "baseball",
    "mlb": "baseball",
    "美國職棒": "baseball",
    "職棒": "baseball",
    "baseball": "baseball",
    "籃球": "basketball",
    "nba": "basketball",
    "美國職籃": "basketball",
    "職籃": "basketball",
    "basketball": "basketball",
    "冰球": "hockey",
    "nhl": "hockey",
    "hockey": "hockey",
    "美式足球": "football",
    "nfl": "football",
    "橄欖球": "football",
    "wbc": "wbc",
    "經典賽": "wbc",
    "世界棒球經典賽": "wbc",
    "棒球經典賽": "wbc",
    "世界棒球": "wbc",
}

# 中文隊名 → 英文隊名對照表
TEAM_ALIASES = {
    # === 國家隊 ===
    "中華台北": ["Chinese Taipei", "TPE", "Taiwan"],
    "台灣": ["Chinese Taipei", "TPE", "Taiwan"],
    "日本": ["Japan", "JPN"],
    "韓國": ["South Korea", "Korea Republic", "KOR"],
    "中國": ["China", "CHN", "China PR"],
    "澳洲": ["Australia", "AUS"],
    "伊朗": ["Iran", "IRN"],
    "沙烏地阿拉伯": ["Saudi Arabia", "KSA"],
    "卡達": ["Qatar", "QAT"],
    "泰國": ["Thailand", "THA"],
    "越南": ["Vietnam", "VIE"],
    "印度": ["India", "IND"],
    "印尼": ["Indonesia", "IDN"],
    "菲律賓": ["Philippines", "PHI"],
    "巴西": ["Brazil", "BRA"],
    "阿根廷": ["Argentina", "ARG"],
    "德國": ["Germany", "GER"],
    "法國": ["France", "FRA"],
    "英格蘭": ["England", "ENG"],
    "西班牙": ["Spain", "ESP"],
    "義大利": ["Italy", "ITA"],
    "荷蘭": ["Netherlands", "NED"],
    "葡萄牙": ["Portugal", "POR"],
    "比利時": ["Belgium", "BEL"],
    "美國": ["United States", "USA"],
    "墨西哥": ["Mexico", "MEX"],
    "哥倫比亞": ["Colombia", "COL"],
    "烏拉圭": ["Uruguay", "URU"],

    # === 英超 ===
    "利物浦": ["Liverpool", "LIV"],
    "曼城": ["Manchester City", "Man City", "MCI"],
    "曼聯": ["Manchester United", "Man United", "MUN"],
    "阿森納": ["Arsenal", "ARS"],
    "兵工廠": ["Arsenal", "ARS"],
    "切爾西": ["Chelsea", "CHE"],
    "熱刺": ["Tottenham", "Tottenham Hotspur", "TOT", "Spurs"],
    "紐卡斯爾": ["Newcastle", "Newcastle United", "NEW"],
    "紐卡索": ["Newcastle", "Newcastle United", "NEW"],
    "阿斯頓維拉": ["Aston Villa", "AVL"],
    "布萊頓": ["Brighton", "BHA"],
    "西漢姆": ["West Ham", "West Ham United", "WHU"],
    "水晶宮": ["Crystal Palace", "CRY"],
    "富勒姆": ["Fulham", "FUL"],
    "狼隊": ["Wolverhampton", "Wolves", "WOL"],
    "伯恩茅斯": ["Bournemouth", "BOU"],
    "諾丁漢森林": ["Nottingham Forest", "Nott'm Forest", "NFO"],
    "布倫特福德": ["Brentford", "BRE"],
    "艾佛頓": ["Everton", "EVE"],
    "萊斯特城": ["Leicester", "Leicester City", "LEI"],

    # === 西甲 ===
    "巴塞隆納": ["Barcelona", "BAR", "Barca"],
    "巴薩": ["Barcelona", "BAR", "Barca"],
    "皇馬": ["Real Madrid", "RMA"],
    "皇家馬德里": ["Real Madrid", "RMA"],
    "馬德里競技": ["Atletico Madrid", "ATM"],
    "馬競": ["Atletico Madrid", "Atl\u00e9tico Madrid", "ATM"],
    "塞維利亞": ["Sevilla", "SEV"],
    "皇家社會": ["Real Sociedad", "RSO"],
    "畢爾包": ["Athletic Bilbao", "Athletic Club", "ATH"],
    "比利亞雷亞爾": ["Villarreal", "VIL"],
    "維拉利爾": ["Villarreal", "VIL"],
    "貝蒂斯": ["Real Betis", "Betis", "BET"],
    "瓦倫西亞": ["Valencia", "VAL"],

    # === 德甲 ===
    "拜仁": ["Bayern Munich", "Bayern", "BAY"],
    "拜仁慕尼黑": ["Bayern Munich", "Bayern", "BAY"],
    "多特蒙德": ["Borussia Dortmund", "Dortmund", "BVB", "DOR"],
    "萊比錫": ["RB Leipzig", "Leipzig", "RBL"],
    "勒沃庫森": ["Bayer Leverkusen", "Leverkusen", "LEV"],
    "法蘭克福": ["Eintracht Frankfurt", "Frankfurt", "SGE"],
    "沃爾夫斯堡": ["Wolfsburg", "WOB"],
    "弗萊堡": ["Freiburg", "SCF"],

    # === 意甲 ===
    "國際米蘭": ["Inter Milan", "Inter", "INT"],
    "AC米蘭": ["AC Milan", "Milan", "ACM"],
    "尤文圖斯": ["Juventus", "JUV"],
    "尤文": ["Juventus", "JUV"],
    "那不勒斯": ["Napoli", "NAP"],
    "拿坡里": ["Napoli", "NAP"],
    "羅馬": ["AS Roma", "Roma", "ROM"],
    "拉齊奧": ["Lazio", "LAZ"],
    "亞特蘭大": ["Atalanta", "ATA"],
    "佛羅倫薩": ["Fiorentina", "FIO"],

    # === 法甲 ===
    "巴黎聖日耳曼": ["Paris Saint-Germain", "PSG", "Paris"],
    "大巴黎": ["Paris Saint-Germain", "PSG", "Paris"],
    "馬賽": ["Marseille", "OM"],
    "里昂": ["Lyon", "OL"],
    "摩納哥": ["Monaco", "MON"],
    "里爾": ["Lille", "LIL"],

    # === MLB ===
    "洋基": ["Yankees", "New York Yankees", "NYY"],
    "紅襪": ["Red Sox", "Boston Red Sox", "BOS"],
    "道奇": ["Dodgers", "Los Angeles Dodgers", "LAD"],
    "大谷": ["Dodgers", "Los Angeles Dodgers", "LAD", "Angels", "Los Angeles Angels"],
    "天使": ["Angels", "Los Angeles Angels", "LAA"],
    "太空人": ["Astros", "Houston Astros", "HOU"],
    "亞特蘭大勇士": ["Braves", "Atlanta Braves", "ATL"],
    "大都會": ["Mets", "New York Mets", "NYM"],
    "費城人": ["Phillies", "Philadelphia Phillies", "PHI"],
    "教士": ["Padres", "San Diego Padres", "SD"],
    "巨人": ["Giants", "San Francisco Giants", "SF"],
    "小熊": ["Cubs", "Chicago Cubs", "CHC"],
    "紅雀": ["Cardinals", "St. Louis Cardinals", "STL"],
    "雙城": ["Twins", "Minnesota Twins", "MIN"],
    "光芒": ["Rays", "Tampa Bay Rays", "TB"],
    "金鶯": ["Orioles", "Baltimore Orioles", "BAL"],
    "藍鳥": ["Blue Jays", "Toronto Blue Jays", "TOR"],
    "水手": ["Mariners", "Seattle Mariners", "SEA"],
    "遊騎兵": ["Rangers", "Texas Rangers", "TEX"],
    "響尾蛇": ["Diamondbacks", "Arizona Diamondbacks", "ARI"],
    "釀酒人": ["Brewers", "Milwaukee Brewers", "MIL"],
    "海盜": ["Pirates", "Pittsburgh Pirates", "PIT"],
    "老虎": ["Tigers", "Detroit Tigers", "DET"],
    "白襪": ["White Sox", "Chicago White Sox", "CWS"],
    "印地安人": ["Guardians", "Cleveland Guardians", "CLE"],
    "守護者": ["Guardians", "Cleveland Guardians", "CLE"],
    "皇家": ["Royals", "Kansas City Royals", "KC"],
    "運動家": ["Athletics", "Oakland Athletics", "OAK"],
    "馬林魚": ["Marlins", "Miami Marlins", "MIA"],
    "紅人": ["Reds", "Cincinnati Reds", "CIN"],
    "國民": ["Nationals", "Washington Nationals", "WSH"],
    "洛磯": ["Rockies", "Colorado Rockies", "COL"],

    # === NBA ===
    "湖人": ["Lakers", "Los Angeles Lakers", "LAL"],
    "塞爾提克": ["Celtics", "Boston Celtics", "BOS"],
    "勇士": ["Warriors", "Golden State Warriors", "GSW"],
    "勇士隊": ["Warriors", "Golden State Warriors", "GSW"],
    "金州勇士": ["Warriors", "Golden State Warriors", "GSW"],
    "快艇": ["Clippers", "Los Angeles Clippers", "LAC"],
    "籃網": ["Nets", "Brooklyn Nets", "BKN"],
    "尼克": ["Knicks", "New York Knicks", "NYK"],
    "七六人": ["76ers", "Philadelphia 76ers", "PHI"],
    "熱火": ["Heat", "Miami Heat", "MIA"],
    "公鹿": ["Bucks", "Milwaukee Bucks", "MIL"],
    "太陽": ["Suns", "Phoenix Suns", "PHX"],
    "獨行俠": ["Mavericks", "Dallas Mavericks", "DAL"],
    "小牛": ["Mavericks", "Dallas Mavericks", "DAL"],
    "雷霆": ["Thunder", "Oklahoma City Thunder", "OKC"],
    "灰狼": ["Timberwolves", "Minnesota Timberwolves", "MIN"],
    "金塊": ["Nuggets", "Denver Nuggets", "DEN"],
    "國王": ["Kings", "Sacramento Kings", "SAC"],
    "鵜鶘": ["Pelicans", "New Orleans Pelicans", "NOP"],
    "暴龍": ["Raptors", "Toronto Raptors", "TOR"],
    "騎士": ["Cavaliers", "Cleveland Cavaliers", "CLE"],
    "活塞": ["Pistons", "Detroit Pistons", "DET"],
    "公牛": ["Bulls", "Chicago Bulls", "CHI"],
    "溜馬": ["Pacers", "Indiana Pacers", "IND"],
    "老鷹": ["Hawks", "Atlanta Hawks", "ATL"],
    "黃蜂": ["Hornets", "Charlotte Hornets", "CHA"],
    "魔術": ["Magic", "Orlando Magic", "ORL"],
    "巫師": ["Wizards", "Washington Wizards", "WAS"],
    "火箭": ["Rockets", "Houston Rockets", "HOU"],
    "馬刺": ["Spurs", "San Antonio Spurs", "SAS"],
    "灰熊": ["Grizzlies", "Memphis Grizzlies", "MEM"],
    "拓荒者": ["Trail Blazers", "Portland Trail Blazers", "POR"],
    "爵士": ["Jazz", "Utah Jazz", "UTA"],

    # === NHL ===
    "企鵝": ["Penguins", "Pittsburgh Penguins", "PIT"],
    "楓葉": ["Maple Leafs", "Toronto Maple Leafs", "TOR"],
    "飛人": ["Flyers", "Philadelphia Flyers", "PHI"],
    "遊騎兵": ["Rangers", "New York Rangers", "NYR"],
    "棟篠人": ["Bruins", "Boston Bruins", "BOS"],
    "紅翼": ["Red Wings", "Detroit Red Wings", "DET"],
    "黑鷹": ["Blackhawks", "Chicago Blackhawks", "CHI"],
    "加人": ["Canadiens", "Montreal Canadiens", "MTL"],
    "油人": ["Oilers", "Edmonton Oilers", "EDM"],
    "火焰": ["Flames", "Calgary Flames", "CGY"],
    "閃電": ["Lightning", "Tampa Bay Lightning", "TBL"],
    "風暴": ["Hurricanes", "Carolina Hurricanes", "CAR"],
    "掀金人": ["Golden Knights", "Vegas Golden Knights", "VGK"],
    "海怪釋放": ["Kraken", "Seattle Kraken", "SEA"],
    "鯊魚": ["Sharks", "San Jose Sharks", "SJS"],
    "野鴨": ["Ducks", "Anaheim Ducks", "ANA"],
    "國王": ["Kings", "Los Angeles Kings", "LAK"],
    "藍衣": ["Blues", "St. Louis Blues", "STL"],
    "星辰": ["Stars", "Dallas Stars", "DAL"],
    "郡狼": ["Coyotes", "Arizona Coyotes", "ARI"],
    "島民": ["Islanders", "New York Islanders", "NYI"],
    "魔鬼": ["Devils", "New Jersey Devils", "NJD"],
    "首都": ["Capitals", "Washington Capitals", "WSH"],
    "藍襲": ["Blue Jackets", "Columbus Blue Jackets", "CBJ"],
    "噴射機": ["Jets", "Winnipeg Jets", "WPG"],
    "可愛的雪崩": ["Avalanche", "Colorado Avalanche", "COL"],
    "野人": ["Wild", "Minnesota Wild", "MIN"],
    "掛布尔可克": ["Predators", "Nashville Predators", "NSH"],

    # === 英超補充 ===
    "曼斯菲爾德": ["Mansfield Town", "Mansfield"],
    "雷克斯漢姆": ["Wrexham"],
    "伊普斯絢奇": ["Ipswich", "Ipswich Town"],
    "南安普敦": ["Southampton"],

    # === 西甲補充 ===
    "奧薩蘇納": ["Osasuna"],
    "馬略卡": ["Mallorca", "RCD Mallorca"],
    "列萬特": ["Levante"],
    "赫羅納": ["Girona"],
    "塞爾塔維戈": ["Celta Vigo", "Celta"],
    "拉斯帕爾馬斯": ["Las Palmas"],
    "阿拉維斯": ["Alaves", "Deportivo Alaves"],
    "菜加利斯": ["Leganes", "CD Leganes"],
    "瓦拉多利德": ["Real Valladolid", "Valladolid"],
    "埃巴爾": ["Espanyol", "RCD Espanyol"],
    "勒尺德": ["Getafe"],
    "拉美尔": ["Rayo Vallecano", "Rayo"],

    # === 德甲補充 ===
    "斯圖加特": ["VfB Stuttgart", "Stuttgart"],
    "美因茲": ["Mainz", "Mainz 05"],
    "海登海姆": ["1. FC Heidenheim 1846", "Heidenheim"],
    "霍芬海姆": ["TSG Hoffenheim", "Hoffenheim"],
    "波魯西亞門興格拉德巴赫": ["Borussia Monchengladbach", "Gladbach", "M'gladbach"],
    "柏林聯合": ["Union Berlin"],
    "不萊梅": ["Werder Bremen", "Bremen"],
    "波鬯姆": ["Bochum", "VfL Bochum"],
    "奥格斯堡": ["FC Augsburg", "Augsburg"],
    "聖保利": ["St. Pauli", "FC St. Pauli"],
    "荷爾斯泰因基爾": ["Holstein Kiel", "Kiel"],

    # === 意甲補充 ===
    "都靈": ["Torino"],
    "薩勒諾": ["Salernitana"],
    "蔇沙索羅": ["Sassuolo"],
    "莱切": ["Lecce"],
    "熱那亞": ["Genoa"],
    "卡利亞里": ["Cagliari"],
    "帕爾馬": ["Parma"],
    "維羅納": ["Verona", "Hellas Verona"],
    "烏迪內斯": ["Udinese"],
    "科莫": ["Como", "Como 1907"],
    "蒙扎": ["Monza"],
    "恩波利": ["Empoli"],
    "威尼斯": ["Venezia"],
    "博洛尼亞": ["Bologna"],

    # === 法甲補充 ===
    "尼斯": ["Nice", "OGC Nice"],
    "雷恩": ["Reims", "Stade de Reims"],
    "布雷斯特": ["Brest", "Stade Brestois"],
    "洛里昂": ["Lorient"],
    "南特": ["Nantes", "FC Nantes"],
    "史特拉斯堡": ["Strasbourg", "RC Strasbourg"],
    "沙特魯": ["Rennes", "Stade Rennais"],
    "土魯斯": ["Toulouse", "Toulouse FC"],
    "安列": ["Angers", "Angers SCO"],
    "聖蒂安": ["Saint-Etienne", "St Etienne", "AS Saint-Etienne"],
    "葢萄園": ["Montpellier", "Montpellier HSC"],
    "哈弗爾": ["Le Havre", "Le Havre AC"],

    # === 其他足球補充 ===
    "漢堡": ["Hamburg SV", "Hamburg", "HSV"],
    "科隆": ["FC Cologne", "Cologne", "Koln"],
    "紐約城": ["New York City FC", "NYCFC"],
    "奧蘭多城": ["Orlando City SC", "Orlando City"],
    "休士頓迪納摩": ["Houston Dynamo FC", "Houston Dynamo"],
    "洛杉磯星河": ["LA Galaxy", "Galaxy"],
    "洛杉磯": ["Los Angeles FC", "LAFC"],
    "亞特蘭大聯": ["Atlanta United", "Atlanta United FC"],
    "西雅圖海灣人": ["Seattle Sounders", "Seattle Sounders FC"],
    "波特蘭伐木工": ["Portland Timbers"],
    "多倫多 FC": ["Toronto FC"],
    "芒特利爾衝擊": ["CF Montreal", "CF Montr\u00e9al"],
    "芬威": ["Fenway"],
    "阿维斯": ["AVS"],
    "卡迪斯亞": ["Al Qadsiah"],
    "體育傑克遜維爾": ["Sporting JAX", "Sporting Jax"],
    "布魯克林": ["Brooklyn FC"],
    "華盛頓力量": ["DC Power FC"],
    "老虎隊": ["Tigres UANL", "Tigres"],
    "蒒特雷": ["Monterrey"],
    "普埃布拉": ["Puebla"],
    "帕丘卡": ["Pachuca"],
    "瓜達拉哈拉": ["Guadalajara", "Chivas"],
    "美洲鵰": ["America", "Am\u00e9rica", "Club America"],
    "阿特拉斯": ["Atlas"],
    "藍十字": ["Cruz Azul"],
    "聖路易斯競技": ["Atl\u00e9tico de San Luis"],
    "克雷塔羅": ["Quer\u00e9taro", "Queretaro"],

    # === 更多國家隊 ===
    "加拿大": ["Canada", "CAN"],
    "智利": ["Chile", "CHI"],
    "秘魯": ["Peru", "PER"],
    "厄瓜多": ["Ecuador", "ECU"],
    "巴拉圭": ["Paraguay", "PAR"],
    "委內瑞拉": ["Venezuela", "VEN"],
    "玉利維亞": ["Bolivia", "BOL"],
    "哥斯大黎加": ["Costa Rica", "CRC"],
    "巴拿馬": ["Panama", "PAN"],
    "牙買加": ["Jamaica", "JAM"],
    "宏都拉斯": ["Honduras", "HON"],
    "薩爾瓦多": ["El Salvador", "SLV"],
    "卡達爾": ["Qatar", "QAT"],
    "阿聯酋": ["United Arab Emirates", "UAE"],
    "奧地利": ["Austria", "AUT"],
    "瑞士": ["Switzerland", "SUI"],
    "克羅埃西亞": ["Croatia", "CRO"],
    "塞爾維亞": ["Serbia", "SRB"],
    "波蘭": ["Poland", "POL"],
    "烏克蘭": ["Ukraine", "UKR"],
    "捷克": ["Czech Republic", "Czechia", "CZE"],
    "土耳其": ["Turkey", "Turkiye", "TUR"],
    "希臘": ["Greece", "GRE"],
    "蛇格蘭": ["Scotland", "SCO"],
    "威爾斯": ["Wales", "WAL"],
    "愛爾蘭": ["Republic of Ireland", "Ireland", "IRL"],
    "北愛爾蘭": ["Northern Ireland", "NIR"],
    "丹麥": ["Denmark", "DEN"],
    "瑞典": ["Sweden", "SWE"],
    "挪威": ["Norway", "NOR"],
    "芬蘭": ["Finland", "FIN"],
    "俄羅斯": ["Russia", "RUS"],
    "奈及利亞": ["Nigeria", "NGA"],
    "喀麥隆": ["Cameroon", "CMR"],
    "塞內加爾": ["Senegal", "SEN"],
    "迭尼及利亞": ["Ghana", "GHA"],
    "埃及": ["Egypt", "EGY"],
    "摩洛哥": ["Morocco", "MAR"],
    "突尼西亞": ["Tunisia", "TUN"],
    "阿爾及利亞": ["Algeria", "ALG"],
    "南非": ["South Africa", "RSA"],
    "紐西蘭": ["New Zealand", "NZL"],
}


# 英文隊名 → 中文隊名（反向對照表，自動從 TEAM_ALIASES 生成）
# 優先使用較短的中文名稱（如「皇馬」而非「皇家馬德里」）
def _build_en_to_cn():
    en_to_cn = {}
    # 先處理較長的中文名，再處理較短的，這樣短的會覆蓋長的
    sorted_aliases = sorted(TEAM_ALIASES.items(), key=lambda x: len(x[0]), reverse=True)
    for cn_name, en_names in sorted_aliases:
        for en in en_names:
            en_lower = en.lower()
            # 跳過純縮寫（3字元以下）
            if len(en) <= 3:
                en_to_cn[en_lower] = cn_name
            else:
                en_to_cn[en_lower] = cn_name
    return en_to_cn

EN_TO_CN = _build_en_to_cn()


# AI 翻譯快取
_ai_cache = {}


def _ai_translate(en_name: str) -> str:
    """用 OpenAI 即時翻譯隊名"""
    if en_name in _ai_cache:
        return _ai_cache[en_name]
    try:
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": f"請將這個體育隊伍名稱翻譯成繁體中文，只回覆中文名稱，不要其他內容：{en_name}"}],
            max_tokens=30,
            temperature=0,
        )
        cn = resp.choices[0].message.content.strip()
        _ai_cache[en_name] = cn
        # 同時加入快取避免重複呼叫
        EN_TO_CN[en_name.lower()] = cn
        return cn
    except:
        _ai_cache[en_name] = en_name
        return en_name


def translate_team_name(en_name: str) -> str:
    """將英文隊名翻譯為中文，找不到則用 AI 翻譯"""
    if not en_name:
        return en_name
    
    # 已經是中文就不翻譯
    if not any(c.isascii() and c.isalpha() for c in en_name):
        return en_name
    
    en_lower = en_name.lower().strip()
    
    # 完全匹配
    if en_lower in EN_TO_CN:
        return EN_TO_CN[en_lower]
    
    # 部分匹配（如 "Houston Astros" 匹配 "astros"）
    for en_key, cn_val in EN_TO_CN.items():
        if len(en_key) > 3 and (en_key in en_lower or en_lower in en_key):
            return cn_val
    
    # 找不到，用 AI 翻譯
    return _ai_translate(en_name)


def find_team_keywords(query: str) -> list:
    """從查詢中提取可能的隊名關鍵字"""
    query = query.strip()
    
    matched_english = []
    for cn_name, en_names in TEAM_ALIASES.items():
        if cn_name in query:
            matched_english.extend(en_names)
    
    if matched_english:
        return matched_english
    
    parts = re.split(r'\s+vs\.?\s+|\s+', query)
    return [p.strip() for p in parts if p.strip()]


def match_event(event: dict, keywords: list) -> bool:
    """檢查賽事是否匹配搜尋關鍵字"""
    competitions = event.get("competitions", [])
    if not competitions:
        return False
    competitors = competitions[0].get("competitors", [])
    
    team_name_sets = []
    for c in competitors:
        team = c.get("team", {})
        names = set()
        for field in ["displayName", "shortDisplayName", "abbreviation", "name", "location"]:
            val = team.get(field, "")
            if val:
                names.add(val.lower())
        team_name_sets.append(names)
    
    event_name = event.get("name", "").lower()
    short_name = event.get("shortName", "").lower()
    
    for kw in keywords:
        kw_lower = kw.lower()
        kw_len = len(kw_lower)
        
        for names in team_name_sets:
            for name in names:
                name_len = len(name)
                if kw_lower == name:
                    return True
                if kw_len <= 3 or name_len <= 3:
                    continue
                if kw_lower in name or name in kw_lower:
                    return True
        
        if kw_len > 4 and (kw_lower in event_name or kw_lower in short_name):
            return True
    
    return False


def parse_user_query(text: str) -> dict:
    """解析使用者查詢，提取隊名和運動類型"""
    # 移除常見的查詢前綴
    prefixes = [
        "我想知道", "查詢", "查比分", "即時比分",
        "目前比分", "現在比分", "比數", "戰況", "查",
        "score", "live", "結果", "怎麼樣了", "比分",
    ]
    
    cleaned = text.strip()
    for p in prefixes:
        if cleaned.startswith(p):
            cleaned = cleaned[len(p):].strip()
    
    # 檢查是否包含運動類型關鍵字
    sport_filter = None
    is_sport_query = False
    remaining = cleaned
    
    for sport_kw, sport_type in SPORT_KEYWORDS.items():
        if sport_kw in cleaned.lower() or sport_kw in cleaned:
            sport_filter = sport_type
            is_sport_query = True
            # 從查詢中移除運動關鍵字，剩下的是隊名
            remaining = re.sub(re.escape(sport_kw), '', cleaned, flags=re.IGNORECASE).strip()
            break
    
    # 分割隊名
    teams = re.split(r'\s+vs\.?\s+|\s+VS\.?\s+|\s+對\s+|\s+和\s+|\s+v\s+', remaining)
    
    if len(teams) == 1:
        parts = remaining.split()
        if len(parts) >= 2:
            teams = parts
        else:
            teams = [remaining] if remaining else []
    
    teams = [t.strip() for t in teams if t.strip()]
    
    # 為每個隊名找到英文關鍵字
    all_keywords = []
    for team in teams:
        keywords = find_team_keywords(team)
        all_keywords.extend(keywords)
    
    if not all_keywords and teams:
        all_keywords = teams
    
    return {
        "original": text,
        "teams": teams,
        "keywords": all_keywords,
        "sport_filter": sport_filter,
        "is_sport_query": is_sport_query,
    }
