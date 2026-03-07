"""
智能隊名語意庫 v1
每支隊伍綁定：聯盟、英文全名、所有中英文別名
"""

# ===== 隊伍資料庫 =====
# 格式：(英文全名, 聯盟, [所有別名（中英文）])

TEAM_DATABASE = [
    # ===== MLB 美國職棒 =====
    ("New York Yankees", "MLB", ["洋基", "紐約洋基", "yankees", "nyy"]),
    ("Boston Red Sox", "MLB", ["紅襪", "波士頓紅襪", "red sox", "bos"]),
    ("Los Angeles Dodgers", "MLB", ["道奇", "洛杉磯道奇", "dodgers", "lad"]),
    ("Houston Astros", "MLB", ["太空人", "休士頓太空人", "astros", "hou"]),
    ("Atlanta Braves", "MLB", ["亞特蘭大勇士", "勇士隊", "braves", "atl"]),
    ("New York Mets", "MLB", ["大都會", "紐約大都會", "mets", "nym"]),
    ("Philadelphia Phillies", "MLB", ["費城人", "phillies", "phi"]),
    ("San Diego Padres", "MLB", ["教士", "聖地牙哥教士", "padres", "sd"]),
    ("Chicago Cubs", "MLB", ["小熊", "芝加哥小熊", "cubs", "chc"]),
    ("St. Louis Cardinals", "MLB", ["紅雀", "聖路易紅雀", "cardinals", "stl"]),
    ("San Francisco Giants", "MLB", ["巨人", "舊金山巨人", "giants", "sf"]),
    ("Seattle Mariners", "MLB", ["水手", "西雅圖水手", "mariners", "sea"]),
    ("Toronto Blue Jays", "MLB", ["藍鳥", "多倫多藍鳥", "blue jays", "tor"]),
    ("Minnesota Twins", "MLB", ["雙城", "明尼蘇達雙城", "twins", "min"]),
    ("Tampa Bay Rays", "MLB", ["光芒", "坦帕灣光芒", "rays", "tb"]),
    ("Baltimore Orioles", "MLB", ["金鶯", "巴爾的摩金鶯", "orioles", "bal"]),
    ("Cleveland Guardians", "MLB", ["乘衛者", "克里夫蘭乘衛者", "guardians", "cle"]),
    ("Texas Rangers", "MLB", ["遊騎兵", "德州遊騎兵", "rangers", "tex"]),
    ("Detroit Tigers", "MLB", ["老虎", "底特律老虎", "tigers", "det"]),
    ("Kansas City Royals", "MLB", ["皇家", "堪薩斯皇家", "royals", "kc"]),
    ("Milwaukee Brewers", "MLB", ["釀酒人", "密爾瓦基釀酒人", "brewers", "mil"]),
    ("Los Angeles Angels", "MLB", ["天使", "洛杉磯天使", "angels", "laa"]),
    ("Chicago White Sox", "MLB", ["白襪", "芝加哥白襪", "white sox", "chw"]),
    ("Arizona Diamondbacks", "MLB", ["響尾蛇", "亞利桑那響尾蛇", "diamondbacks", "ari"]),
    ("Pittsburgh Pirates", "MLB", ["海盜", "匹茲堡海盜", "pirates", "pit"]),
    ("Cincinnati Reds", "MLB", ["紅人", "辛辛那提紅人", "reds", "cin"]),
    ("Miami Marlins", "MLB", ["馬林魚", "邁阿密馬林魚", "marlins", "mia"]),
    ("Washington Nationals", "MLB", ["國民", "華盛頓國民", "nationals", "wsh"]),
    ("Colorado Rockies", "MLB", ["洛磯", "科羅拉多洛磯", "rockies", "col"]),
    ("Oakland Athletics", "MLB", ["運動家", "奧克蘭運動家", "athletics", "oak"]),

    # ===== NBA 美國職籃 =====
    ("Los Angeles Lakers", "NBA", ["湖人", "洛杉磯湖人", "lakers", "lal"]),
    ("Golden State Warriors", "NBA", ["勇士", "金州勇士", "warriors", "gsw"]),
    ("Boston Celtics", "NBA", ["塞爾提克", "波士頓塞爾提克", "celtics", "bos"]),
    ("Milwaukee Bucks", "NBA", ["公鹿", "密爾瓦基公鹿", "bucks", "mil"]),
    ("Denver Nuggets", "NBA", ["金塊", "丹佛金塊", "nuggets", "den"]),
    ("Phoenix Suns", "NBA", ["太陽", "鳳凰城太陽", "suns", "phx"]),
    ("Philadelphia 76ers", "NBA", ["七六人", "費城七六人", "76ers", "sixers", "phi"]),
    ("Miami Heat", "NBA", ["熱火", "邁阿密熱火", "heat", "mia"]),
    ("Dallas Mavericks", "NBA", ["獨行俠", "達拉斯獨行俠", "mavericks", "mavs", "dal"]),
    ("Brooklyn Nets", "NBA", ["籃網", "布魯克林籃網", "nets", "bkn"]),
    ("New York Knicks", "NBA", ["尼克", "紐約尼克", "knicks", "nyk"]),
    ("Chicago Bulls", "NBA", ["公牛", "芝加哥公牛", "bulls", "chi"]),
    ("Cleveland Cavaliers", "NBA", ["騎士", "克里夫蘭騎士", "cavaliers", "cavs", "cle"]),
    ("Oklahoma City Thunder", "NBA", ["雷霆", "奧克拉荷馬雷霆", "thunder", "okc"]),
    ("Sacramento Kings", "NBA", ["國王", "沙加緬度國王", "kings", "sac"]),
    ("Indiana Pacers", "NBA", ["溜馬", "印第安納溜馬", "pacers", "ind"]),
    ("Minnesota Timberwolves", "NBA", ["灰狼", "明尼蘇達灰狼", "timberwolves", "wolves", "min"]),
    ("New Orleans Pelicans", "NBA", ["鵜鶘", "紐奧良鵜鶘", "pelicans", "nop"]),
    ("Memphis Grizzlies", "NBA", ["灰熊", "曼菲斯灰熊", "grizzlies", "mem"]),
    ("Atlanta Hawks", "NBA", ["老鷹", "亞特蘭大老鷹", "hawks", "atl"]),
    ("Toronto Raptors", "NBA", ["暴龍", "多倫多暴龍", "raptors", "tor"]),
    ("Houston Rockets", "NBA", ["火箭", "休士頓火箭", "rockets", "hou"]),
    ("San Antonio Spurs", "NBA", ["馬刺", "聖安東尼奧馬刺", "spurs", "sas"]),
    ("Portland Trail Blazers", "NBA", ["拓荒者", "波特蘭拓荒者", "trail blazers", "blazers", "por"]),
    ("Utah Jazz", "NBA", ["爵士", "猶他爵士", "jazz", "uta"]),
    ("Orlando Magic", "NBA", ["魔術", "奧蘭多魔術", "magic", "orl"]),
    ("Charlotte Hornets", "NBA", ["黃蜂", "夏洛特黃蜂", "hornets", "cha"]),
    ("Detroit Pistons", "NBA", ["活塞", "底特律活塞", "pistons", "det"]),
    ("Washington Wizards", "NBA", ["巫師", "華盛頓巫師", "wizards", "wiz"]),
    ("Los Angeles Clippers", "NBA", ["快艇", "洛杉磯快艇", "clippers", "lac"]),

    # ===== NHL 冰球 =====
    ("New York Rangers", "NHL", ["遊騎兵隊", "紐約遊騎兵", "rangers", "nyr"]),
    ("New Jersey Devils", "NHL", ["魔鬼", "紐澤西魔鬼", "devils", "njd"]),
    ("Boston Bruins", "NHL", ["棕熊", "波士頓棕熊", "bruins", "bos"]),
    ("Toronto Maple Leafs", "NHL", ["楓葉", "多倫多楓葉", "maple leafs", "tor"]),
    ("Montreal Canadiens", "NHL", ["加拿大人", "蒙特婁加拿大人", "canadiens", "habs", "mtl"]),
    ("Tampa Bay Lightning", "NHL", ["閃電", "坦帕灣閃電", "lightning", "tbl"]),
    ("Florida Panthers", "NHL", ["美洲豹", "佛羅里達美洲豹", "panthers", "fla"]),
    ("Pittsburgh Penguins", "NHL", ["企鵝", "匹茲堡企鵝", "penguins", "pit"]),
    ("Washington Capitals", "NHL", ["首都", "華盛頓首都", "capitals", "caps", "wsh"]),
    ("Carolina Hurricanes", "NHL", ["颶風", "卡羅萊納颶風", "hurricanes", "canes", "car"]),
    ("New York Islanders", "NHL", ["島民", "紐約島民", "islanders", "nyi"]),
    ("Detroit Red Wings", "NHL", ["紅翼", "底特律紅翼", "red wings", "det"]),
    ("Chicago Blackhawks", "NHL", ["黑鷹", "芝加哥黑鷹", "blackhawks", "chi"]),
    ("Colorado Avalanche", "NHL", ["雪崩", "科羅拉多雪崩", "avalanche", "avs", "col"]),
    ("Dallas Stars", "NHL", ["星辰", "達拉斯星辰", "stars", "dal"]),
    ("Edmonton Oilers", "NHL", ["油人", "艾德蒙頓油人", "oilers", "edm"]),
    ("Vegas Golden Knights", "NHL", ["金騎士", "維加斯金騎士", "golden knights", "vgk"]),
    ("Winnipeg Jets", "NHL", ["噴射機", "溫尼伯噴射機", "jets", "wpg"]),
    ("Minnesota Wild", "NHL", ["乖僻", "明尼蘇達乖僻", "wild", "min"]),
    ("Vancouver Canucks", "NHL", ["乖乖鯨", "溫哥華加人", "canucks", "van"]),
    ("Calgary Flames", "NHL", ["火焰", "卡加利火焰", "flames", "cgy"]),
    ("Ottawa Senators", "NHL", ["參議員", "渥太華參議員", "senators", "ott"]),
    ("San Jose Sharks", "NHL", ["鯊魚", "聖荷西鯊魚", "sharks", "sjs"]),
    ("Philadelphia Flyers", "NHL", ["飛人", "費城飛人", "flyers", "phi"]),
    ("Los Angeles Kings", "NHL", ["國王隊", "洛杉磯國王", "la kings", "lak"]),
    ("Anaheim Ducks", "NHL", ["鴨子", "安乃翰鴨子", "ducks", "ana"]),
    ("Nashville Predators", "NHL", ["掠食者", "乃許維爾掠食者", "predators", "preds", "nsh"]),
    ("St. Louis Blues", "NHL", ["藍調", "聖路易藍調", "blues", "stl"]),
    ("Columbus Blue Jackets", "NHL", ["藍夾克", "哥倫布藍夾克", "blue jackets", "cbj"]),
    ("Buffalo Sabres", "NHL", ["軍刀", "水牛城軍刀", "sabres", "buf"]),
    ("Seattle Kraken", "NHL", ["海怪", "西雅圖海怪", "kraken", "sea"]),
    ("Utah Hockey Club", "NHL", ["猶他冰球", "utah hockey", "uta"]),

    # ===== NFL 美式足球 =====
    ("Kansas City Chiefs", "NFL", ["酋長", "堪薩斯酋長", "chiefs", "kc"]),
    ("San Francisco 49ers", "NFL", ["乃拿斯", "舊金山乃拿斯", "49ers", "niners", "sf"]),
    ("Philadelphia Eagles", "NFL", ["老鷹隊", "費城老鷹", "eagles", "phi"]),
    ("Dallas Cowboys", "NFL", ["牛仔", "達拉斯牛仔", "cowboys", "dal"]),
    ("Buffalo Bills", "NFL", ["比爾", "水牛城比爾", "bills", "buf"]),
    ("Baltimore Ravens", "NFL", ["乃鴉", "巴爾的摩乃鴉", "ravens", "bal"]),
    ("Detroit Lions", "NFL", ["獅子", "底特律獅子", "lions", "det"]),
    ("Green Bay Packers", "NFL", ["乃裝工", "綠灣乃裝工", "packers", "gb"]),

    # ===== 英超 =====
    ("Liverpool", "英超", ["利物浦", "liverpool", "lfc"]),
    ("Manchester City", "英超", ["曼城", "manchester city", "man city", "mcfc"]),
    ("Arsenal", "英超", ["兵工廠", "阿森納", "arsenal", "afc"]),
    ("Chelsea", "英超", ["切爾西", "chelsea", "cfc"]),
    ("Manchester United", "英超", ["曼聯", "manchester united", "man utd", "mufc"]),
    ("Tottenham Hotspur", "英超", ["熱刺", "tottenham", "spurs", "thfc"]),
    ("Newcastle United", "英超", ["紐卡索", "紐卡斯爾", "newcastle", "nufc"]),
    ("Aston Villa", "英超", ["阿斯頓維拉", "維拉", "aston villa", "avfc"]),
    ("Brighton & Hove Albion", "英超", ["布萊頓", "brighton"]),
    ("West Ham United", "英超", ["西漢姆", "west ham", "whu"]),
    ("Wolverhampton Wanderers", "英超", ["狼隊", "wolves", "wolverhampton"]),
    ("Bournemouth", "英超", ["伯恩茅斯", "bournemouth"]),
    ("Crystal Palace", "英超", ["水晶宮", "crystal palace"]),
    ("Fulham", "英超", ["富勒姆", "fulham"]),
    ("Everton", "英超", ["艾佛頓", "everton"]),
    ("Brentford", "英超", ["布倫特福德", "brentford"]),
    ("Nottingham Forest", "英超", ["諾丁漢森林", "nottingham", "forest"]),
    ("Leicester City", "英超", ["萊斯特城", "leicester"]),
    ("Ipswich Town", "英超", ["伊普斯維奇", "ipswich"]),
    ("Southampton", "英超", ["南安普頓", "southampton"]),

    # ===== 西甲 =====
    ("Real Madrid", "西甲", ["皇馬", "皇家馬德里", "real madrid"]),
    ("Barcelona", "西甲", ["巴薩", "巴塞隆納", "barcelona", "barca"]),
    ("Atletico Madrid", "西甲", ["馬競", "馬德里競技", "atletico"]),
    ("Real Sociedad", "西甲", ["皇家社會", "real sociedad", "sociedad"]),
    ("Real Betis", "西甲", ["皇家貝蒂斯", "betis"]),
    ("Athletic Bilbao", "西甲", ["畢爾包", "bilbao"]),
    ("Villarreal", "西甲", ["比利亞雷亞爾", "黃色潛水艇", "villarreal"]),
    ("Sevilla", "西甲", ["塞維利亞", "sevilla"]),
    ("Valencia", "西甲", ["瓦倫西亞", "valencia"]),
    ("Girona", "西甲", ["赫羅納", "girona"]),

    # ===== 德甲 =====
    ("Bayern Munich", "德甲", ["拜仁", "拜仁慕尼黑", "bayern", "bayern munich"]),
    ("Borussia Dortmund", "德甲", ["多特蒙德", "dortmund", "bvb"]),
    ("RB Leipzig", "德甲", ["萊比錫", "leipzig"]),
    ("Bayer Leverkusen", "德甲", ["勒沃庫森", "leverkusen"]),
    ("Eintracht Frankfurt", "德甲", ["法蘭克福", "frankfurt"]),
    ("VfB Stuttgart", "德甲", ["斯圖加特", "stuttgart"]),

    # ===== 意甲 =====
    ("Inter Milan", "意甲", ["國際米蘭", "國米", "inter"]),
    ("AC Milan", "意甲", ["AC米蘭", "米蘭", "ac milan"]),
    ("Juventus", "意甲", ["尤文", "尤文圖斯", "juventus", "juve"]),
    ("Napoli", "意甲", ["拿坡里", "那不勒斯", "napoli"]),
    ("AS Roma", "意甲", ["羅馬", "roma"]),
    ("Lazio", "意甲", ["拉齊奧", "lazio"]),
    ("Atalanta", "意甲", ["亞特蘭大", "atalanta"]),
    ("Fiorentina", "意甲", ["佛羅倫薩", "fiorentina"]),

    # ===== 法甲 =====
    ("Paris Saint-Germain", "法甲", ["巴黎聖日耳曼", "大巴黎", "psg"]),
    ("Marseille", "法甲", ["馬賽", "marseille"]),
    ("Lyon", "法甲", ["里昂", "lyon"]),
    ("Monaco", "法甲", ["摩納哥", "monaco"]),
    ("Lille", "法甲", ["里爾", "lille"]),

    # ===== WBC 世界棒球經典賽（國家隊）=====
    ("Chinese Taipei", "WBC", ["中華台北", "台灣", "chinese taipei", "tpe", "tpo"]),
    ("Japan", "WBC", ["日本", "japan", "jpn"]),
    ("Korea", "WBC", ["韓國", "南韓", "korea", "kor"]),
    ("United States", "WBC", ["美國", "美國隊", "usa", "united states"]),
    ("Dominican Republic", "WBC", ["多明尼加", "dominican republic", "dom"]),
    ("Venezuela", "WBC", ["委內瑞拉", "venezuela", "ven"]),
    ("Cuba", "WBC", ["古巴", "cuba", "cub"]),
    ("Puerto Rico", "WBC", ["波多黎各", "puerto rico", "pur"]),
    ("Mexico", "WBC", ["墨西哥", "mexico", "mex"]),
    ("Netherlands", "WBC", ["荷蘭", "netherlands", "ned"]),
    ("Australia", "WBC", ["澳洲", "australia", "aus"]),
    ("Canada", "WBC", ["加拿大", "canada", "can"]),
    ("Colombia", "WBC", ["哥倫比亞", "colombia", "col"]),
    ("Italy", "WBC", ["義大利", "意大利", "italy", "ita"]),
    ("Panama", "WBC", ["巴拿馬", "panama", "pan"]),
    ("Israel", "WBC", ["以色列", "israel", "isr"]),
    ("Great Britain", "WBC", ["英國", "great britain", "gbr"]),
    ("Nicaragua", "WBC", ["尼加拉瓜", "nicaragua", "nic"]),
    ("Brazil", "WBC", ["巴西", "brazil", "bra"]),
    ("Czechia", "WBC", ["捷克", "czechia", "czech republic", "cze"]),
    ("India", "WBC", ["印度", "india", "ind"]),
    ("Vietnam", "WBC", ["越南", "vietnam", "vie"]),

    # ===== 足球國家隊（非 WBC）=====
    ("Germany", "足球", ["德國", "germany", "ger"]),
    ("France", "足球", ["法國", "france", "fra"]),
    ("England", "足球", ["英格蘭", "england", "eng"]),
    ("Spain", "足球", ["西班牙", "spain", "esp"]),
    ("Argentina", "足球", ["阿根廷", "argentina", "arg"]),
    ("Portugal", "足球", ["葡萄牙", "portugal", "por"]),
    ("Belgium", "足球", ["比利時", "belgium", "bel"]),
    ("Croatia", "足球", ["克羅埃西亞", "croatia", "cro"]),
    ("Uruguay", "足球", ["烏拉圭", "uruguay", "uru"]),
    ("Saudi Arabia", "足球", ["沙烏地阿拉伯", "saudi arabia", "ksa"]),
    ("Iran", "足球", ["伊朗", "iran", "irn"]),
    ("Thailand", "足球", ["泰國", "thailand", "tha"]),
    ("China PR", "足球", ["中國", "china", "chn"]),
]


# ===== 建立索引 =====

# 別名 → (英文全名, 聯盟, 中文首選名)
ALIAS_INDEX = {}
# 英文全名 → 中文首選名
EN_TO_CN = {}
# 聯盟 → ESPN 端點
LEAGUE_TO_ENDPOINT = {
    "MLB": ("baseball", "mlb"),
    "NBA": ("basketball", "nba"),
    "NHL": ("hockey", "nhl"),
    "NFL": ("football", "nfl"),
    "WBC": ("baseball", "world-baseball-classic"),
    "英超": ("soccer", "eng.1"),
    "西甲": ("soccer", "esp.1"),
    "德甲": ("soccer", "ger.1"),
    "意甲": ("soccer", "ita.1"),
    "法甲": ("soccer", "fra.1"),
    "足球": ("soccer", "all"),
}

# 所有中文別名列表（用於模糊搜尋）
ALL_CN_ALIASES = []
# 所有英文別名列表（用於模糊搜尋）
ALL_EN_ALIASES = []

for en_name, league, aliases in TEAM_DATABASE:
    cn_primary = aliases[0]  # 第一個別名作為中文首選名
    EN_TO_CN[en_name.lower()] = cn_primary

    for alias in aliases:
        alias_lower = alias.lower()
        ALIAS_INDEX[alias_lower] = {
            "en_name": en_name,
            "league": league,
            "cn_name": cn_primary,
        }

        # 分類中英文
        if any('\u4e00' <= c <= '\u9fff' for c in alias):
            ALL_CN_ALIASES.append(alias)
        else:
            ALL_EN_ALIASES.append(alias)


def get_cn_name(en_display_name: str) -> str:
    """英文隊名 → 中文名"""
    key = en_display_name.lower()
    if key in EN_TO_CN:
        return EN_TO_CN[key]
    # 嘗試部分匹配
    for en_full, cn in EN_TO_CN.items():
        if key in en_full or en_full in key:
            return cn
    return en_display_name  # 找不到就回傳原名
