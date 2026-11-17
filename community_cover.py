"""Original LA1 daily cover, rendered from the same verified article fields."""
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def daily_cover(text):
    basketball = '每日籃球' in text
    accent = '#ffad46' if basketball else '#54e3ac'
    image = Image.new('RGB', (1200, 630), '#0a1720')
    draw = ImageDraw.Draw(image)
    fonts = ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
             'C:/Windows/Fonts/arialbd.ttf']
    font_path = next((x for x in fonts if Path(x).exists()), None)
    def font(size):
        return ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default(size=size)
    draw.rounded_rectangle((38,38,1162,592), radius=35, outline=accent, width=3)
    draw.text((78,65), 'LA1', font=font(70), fill=accent)
    draw.text((280,86), 'BASKETBALL' if basketball else 'FOOTBALL', font=font(42), fill='white')
    draw.text((80,175), 'DAILY MATCH DISCUSSION', font=font(24), fill=accent)
    rows = [line for line in text.splitlines() if ' vs ' in line and not line.startswith('[')][:3]
    times = [line.split('|')[0] for line in text.splitlines() if 'UTC+8｜' in line][:3]
    for i, row in enumerate(rows):
        y = 245+i*99
        size = 32
        while draw.textlength(row, font=font(size)) > 1030 and size > 16:
            size -= 1
        draw.text((80,y),row,font=font(size),fill='white')
        if i < len(times):
            draw.text((80,y+43),times[i].split('｜')[0],font=font(19),fill=accent)
    if not rows:
        draw.text((80,280),'MATCHDAY REVIEW & COMMUNITY TALK',font=font(30),fill='white')
    draw.text((80,550),'ESPN DATA  /  UTC+8  /  LA1 COMMUNITY',font=font(18),fill='#a7bac5')
    output=BytesIO()
    image.save(output,format='PNG')
    output.seek(0)
    output.name='la1-daily.png'
    return output
