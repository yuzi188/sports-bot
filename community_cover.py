"""Traditional Chinese schedule generated from the same snapshot as its caption."""
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def daily_cover(post):
    font_path = next((p for p in ['/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', 'C:/Windows/Fonts/msjhbd.ttc'] if Path(p).exists()), None)
    if not font_path:
        raise RuntimeError('CJK_font_missing')
    basketball = post['sport'] == 'basketball'
    accent = (255,163,65) if basketball else (235,204,113)
    im = Image.new('RGB',(1080,1350),(10,20,39) if basketball else (7,39,32))
    d = ImageDraw.Draw(im)
    def text(x,y,value,size=36,color='white',width=None,anchor=None):
        font = ImageFont.truetype(font_path,size)
        while width and d.textlength(value,font=font)>width and size>16:
            size-=1
            font=ImageFont.truetype(font_path,size)
        d.text((x,y),value,font=font,fill=color,anchor=anchor)
    for inset in (24,40):
        d.rounded_rectangle((inset,inset,1080-inset,1350-inset),radius=30,outline=accent,width=2)
    d.ellipse((220,420,860,1060),outline=(40,66,70),width=4)
    d.line((60,740,1020,740),fill=(40,66,70),width=3)
    text(64,65,'LA1  /  MATCHDAY',34,accent)
    text(64,125,'NBA 焦點賽程' if basketball else '足球焦點賽程',72)
    text(64,230,post['date'].replace('-',' / '),38,accent)
    text(64,295,'香港時間 UTC+8  ·  客隊 vs 主隊',28)
    def crown(cx,y):
        d.polygon([(cx-27,y),(cx-16,y+15),(cx,y-8),(cx+16,y+15),(cx+27,y),(cx+21,y+29),(cx-21,y+29)],fill=accent)
        d.rectangle((cx-21,y+32,cx+21,y+37),fill=accent)
    for i,row in enumerate(post['fixtures']):
        top=365+i*160
        d.rounded_rectangle((60,top,1020,top+144),radius=16,fill=(16,31,47) if basketball else (12,54,43),outline=accent,width=2)
        text(82,top+15,f'{i+1:02}',26,accent)
        text(143,top+14,row['local_start']+'  '+row['label'],25,accent,width=820)
        for side,cx in [('away',350),('home',790)]:
            if row['choice']==side:
                crown(cx,top+46)
            text(cx,top+101,row[side+'_zh'],40,width=335,anchor='mm')
        text(562,top+101,'VS',28,accent,anchor='mm')
        if row['choice'] in ('pass','draw'):
            text(970,top+120,'觀望' if row['choice']=='pass' else '和局',19,accent,anchor='rm')
    text(64,1200,'皇冠＝賽前觀點・非賽果',30,accent)
    text(64,1250,'賽程・逐場觀點・整單討論',25)
    output=BytesIO()
    im.save(output,'PNG')
    output.seek(0)
    output.name='la1-schedule.png'
    return output
