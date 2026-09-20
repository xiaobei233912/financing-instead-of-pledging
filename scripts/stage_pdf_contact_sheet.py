from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
P=Path(__file__).parent.parent/'tmp'/'pdfs'/'stage'
files=sorted(P.glob('page-*.png'))
for batch in range((len(files)+8)//9):
    group=files[batch*9:batch*9+9]
    board=Image.new('RGB',(990,1450),'#bdc8cc');draw=ImageDraw.Draw(board)
    for i,path in enumerate(group):
        img=Image.open(path).convert('RGB');img.thumbnail((310,430))
        x=15+(i%3)*330;y=25+(i//3)*480
        board.paste(img,(x,y));draw.text((x,y+435),path.stem,fill='black')
    board.save(P/f'contact-{batch+1}.jpg')
