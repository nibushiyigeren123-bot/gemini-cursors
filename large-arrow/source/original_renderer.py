"""Rebuild all five sizes and 17 ANI states from the editable pose sources."""
from pathlib import Path
import hashlib
import json
import math
from PIL import Image, ImageDraw, ImageFont
import cursor_codec as codec

REPO = Path(__file__).resolve().parents[1]
PROFILE = json.loads((REPO / 'source/package.json').read_text(encoding='utf-8'))
SIZES = (32,48,64,128,256)
ROLE_POSE = {'Arrow':'idle','Help':'review','AppStarting':'waiting','Wait':'working','Crosshair':'review','IBeam':'working','NWPen':'working','No':'failed','SizeNS':'jumping','SizeWE':'walking-right','SizeNWSE':'walking-right','SizeNESW':'walking-left','SizeAll':'walking-right','UpArrow':'jumping','Hand':'waving','Pin':'waiting','Person':'waving'}
CACHE = {}

def action_frame(character, pose, frame):
    key = (character, pose)
    if key not in CACHE:
        raw = Image.open(REPO / 'source/characters' / character / 'pose-sources' / (pose + '.png')).convert('RGBA')
        box = raw.getbbox()
        assert box
        raw = raw.crop(box)
        factor = min(224/raw.width,224/raw.height)
        CACHE[key] = raw.resize((round(raw.width*factor),round(raw.height*factor)),Image.Resampling.LANCZOS)
    raw = CACHE[key]
    t = 2*math.pi*(frame % 8)/8
    angle = math.sin(t)*(2.0 if pose.startswith('walking') else 1.4 if pose in ('waving','failed') else 0.6)
    figure = raw.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    # Eight continuous phases are procedural 2D motion from a drawn pose, not
    # claimed to be independent hand-drawn walk-cycle or motion-capture frames.
    dy = round((1-math.cos(t))*7) if pose == 'jumping' else round(math.sin(t)*2)
    dx = round(math.sin(t)*3) if pose.startswith('walking') else 0
    canvas = Image.new('RGBA',(256,256))
    x = (256-figure.width)//2 + dx
    y = 245-figure.height-dy
    assert x >= 0 and y >= 0 and x+figure.width <= 256 and y+figure.height <= 256
    canvas.alpha_composite(figure,(x,y))
    return canvas

def compile_frame(character, role, size, frame=0):
    canvas = action_frame(character,ROLE_POSE[role],frame)
    codec.MINT = PROFILE['accent']
    icon, hot = codec.symbol(role,frame)
    box = icon.getbbox()
    badge = icon.crop(box)
    factor = 62/max(badge.size)
    badge = badge.resize((round(badge.width*factor),round(badge.height*factor)),Image.Resampling.LANCZOS)
    canvas.alpha_composite(badge,(3,3))
    result = canvas.resize((size,size),Image.Resampling.LANCZOS)
    hotspot = tuple(max(0,min(size-1,round(((value*4-box[axis])*factor+3)*size/256))) for axis,value in enumerate(hot))
    return result,hotspot

def main():
    entries = []
    previews = REPO/'previews'
    previews.mkdir(exist_ok=True)
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
    for character in PROFILE['characters']:
        cid = character['id']
        for size in SIZES:
            for role,label in codec.ROLES:
                images = []
                for frame in range(8):
                    image,hotspot = compile_frame(cid,role,size,frame)
                    images.append(image)
                    target = REPO/f'source/frames/{cid}/{size}/{role}-{frame:02}.png'
                    target.parent.mkdir(parents=True,exist_ok=True)
                    image.save(target)
                target = REPO/f'cursors/{cid}/{size}/{role}.ani'
                target.parent.mkdir(parents=True,exist_ok=True)
                speed = 12 if role == 'Arrow' else 8
                target.write_bytes(codec.ani_bytes(images,hotspot,speed))
                entries.append({'character':cid,'size':size,'role':role,'label':label,'file':target.relative_to(REPO).as_posix(),'hotspot':list(hotspot),'frames':8,'jiffies':speed,'frame_ms':speed*1000/60,'action':ROLE_POSE[role]})
        sheet = Image.new('RGB',(1440,520),'#142239')
        d = ImageDraw.Draw(sheet)
        d.text((24,14),character['display']+' · 全部17状态 / 64px',font=font,fill='white')
        for i,(role,label) in enumerate(codec.ROLES):
            x=20+(i%9)*158;y=60+(i//9)*218
            light=Image.new('RGB',(70,74),'#f1f6fa');dark=Image.new('RGB',(70,74),'#142239')
            im,_=compile_frame(cid,role,64)
            light.paste(im,(3,5),im);dark.paste(im,(3,5),im)
            sheet.paste(light,(x,y));sheet.paste(dark,(x+72,y))
            d.text((x,y+87),label,font=font,fill='white')
            d.text((x,y+115),role,font=font,fill='#aac4e8')
        sheet.save(previews/(cid+'-overview.png'))
        panels=[]
        for frame in range(8):
            card=Image.new('RGB',(1020,180),'#142239');d=ImageDraw.Draw(card)
            for i,role in enumerate(['Arrow','Help','Wait','Hand','SizeAll','SizeNS','No']):
                im,_=compile_frame(cid,role,96,frame);card.paste(im,(i*144+8,56),im)
                d.text((i*144+8,16),dict(codec.ROLES)[role],font=font,fill='white')
            panels.append(card)
        panels[0].save(previews/(cid+'-animation.gif'),save_all=True,append_images=panels[1:],duration=150,loop=0,disposal=2)
    (REPO/'source/cursor_manifest.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding='utf-8')
    recipe={'motion':'9 illustrated poses with 8-phase breathing, slight tilt, sway and jump offset', 'hand_drawn_cycle':False,'role_pose':ROLE_POSE,'sizes':SIZES,'full_body_max':224,'symbol_max':62,'frames_per_state':8,'raw_sources_preserved':True}
    (REPO/'source/action-recipe.json').write_text(json.dumps(recipe,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'repo':PROFILE['repository'],'characters':len(PROFILE['characters']),'ani':len(entries),'png_frames':len(entries)*8},ensure_ascii=False))

if __name__ == '__main__':
    main()
