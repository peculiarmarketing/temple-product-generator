import sys
from PIL import Image,ImageDraw,ImageFont
out=sys.argv[1];names=sys.argv[2:]
f=ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc",26);W,H=1000,667;cols=2
rows=(len(names)+1)//2
sh=Image.new('RGB',(cols*W,rows*(H+40)),'white');dr=ImageDraw.Draw(sh)
for i,n in enumerate(names):
    im=Image.open(n).convert('RGB');lab=f"{n}  {im.size[0]}x{im.size[1]}";im.thumbnail((W-10,H-10))
    x=(i%cols)*W;y=(i//cols)*(H+40);sh.paste(im,(x+5,y+5));dr.text((x+10,y+H+4),lab,fill='black',font=f)
sh.save(out,quality=85)
