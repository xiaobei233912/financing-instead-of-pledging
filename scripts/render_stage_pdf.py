from pathlib import Path
import json,html
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Table,TableStyle,Image,KeepTogether

ROOT=Path(__file__).parent.parent;P=ROOT/'results'/'cash_relay_stage';OUT=ROOT/'output'/'pdf';OUT.mkdir(parents=True,exist_ok=True)
pdfmetrics.registerFont(TTFont('CN','C:/Windows/Fonts/msyh.ttc',subfontIndex=0))
pdfmetrics.registerFont(TTFont('CN-Bold','C:/Windows/Fonts/msyhbd.ttc',subfontIndex=0))
pdfmetrics.registerFontFamily('CN',normal='CN',bold='CN-Bold',italic='CN',boldItalic='CN-Bold')
ink=colors.HexColor('#203642');accent=colors.HexColor('#16728b');muted=colors.HexColor('#60747d');light=colors.HexColor('#edf4f6')
styles={
 'body':ParagraphStyle('body',fontName='CN',fontSize=10.6,leading=17.2,textColor=ink,spaceAfter=10,wordWrap='CJK'),
 'title':ParagraphStyle('title',fontName='CN-Bold',fontSize=20,leading=29,textColor=ink,spaceAfter=18,wordWrap='CJK'),
 'cover':ParagraphStyle('cover',fontName='CN-Bold',fontSize=35,leading=47,textColor=ink,spaceAfter=25,wordWrap='CJK'),
 'sub':ParagraphStyle('sub',fontName='CN-Bold',fontSize=11.4,leading=17,textColor=accent,spaceBefore=6,spaceAfter=8,wordWrap='CJK',keepWithNext=True),
 'small':ParagraphStyle('small',fontName='CN',fontSize=7.4,leading=11.4,textColor=muted,spaceAfter=7,wordWrap='CJK'),
 'cell':ParagraphStyle('cell',fontName='CN',fontSize=8.5,leading=12.5,textColor=ink,wordWrap='CJK'),
 'head':ParagraphStyle('head',fontName='CN-Bold',fontSize=8.5,leading=12.5,textColor=colors.white,wordWrap='CJK'),
 'compactcell':ParagraphStyle('compactcell',fontName='CN',fontSize=7.6,leading=11.3,textColor=ink,wordWrap='CJK'),
 'compacthead':ParagraphStyle('compacthead',fontName='CN-Bold',fontSize=7.7,leading=11.4,textColor=colors.white,wordWrap='CJK'),
}
page_w,page_h=A4;left=44;right=44;width=page_w-left-right
def para(text,style='body'):return Paragraph(html.escape(str(text)).replace('\n','<br/>'),styles[style])
def make_table(block):
    weights=block.get('widths') or [1]*len(block['head'])
    widths=[width*w/sum(weights) for w in weights]
    compact=len(block['rows'])>20 or len(block['head'])>=7
    data=[[para(x,'compacthead' if compact else 'head') for x in block['head']]]+[[para(x,'compactcell' if compact else 'cell') for x in row] for row in block['rows']]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    pad=3 if len(block['rows'])>20 else 5
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),accent),('ROWBACKGROUNDS',(0,1),(-1,-1),[light,colors.white]),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
        ('TOPPADDING',(0,0),(-1,-1),pad),('BOTTOMPADDING',(0,0),(-1,-1),pad),
        ('LINEBELOW',(0,-1),(-1,-1),.4,colors.HexColor('#d4e2e6'))]))
    return t

def page(canvas,doc):
    canvas.saveState()
    canvas.setFillColor(accent);canvas.rect(left,page_h-31,28,3,fill=1,stroke=0)
    canvas.setFont('CN',8);canvas.setFillColor(muted)
    canvas.drawString(left+38,page_h-31,'现金接力  /  阶段性研究报告')
    canvas.setStrokeColor(colors.HexColor('#d4e2e6'));canvas.line(left,36,page_w-right,36)
    canvas.setFont('CN',7.2);canvas.drawString(left,23,'2026-09-12  ·  历史代理与规则模拟  ·  数据截至2026-09-08')
    canvas.drawRightString(page_w-right,23,str(doc.page))
    canvas.restoreState()

sections=json.loads((P/'report_sections.json').read_text(encoding='utf-8'));story=[]
for idx,s in enumerate(sections):
    if idx:story.append(PageBreak())
    if idx==0:
        story.append(Spacer(1,40));story.append(para(s['kicker'],'sub'));story.append(para(s['title'],'cover'))
    else:
        title=para(s['title'],'title');title.bookmark=('section_'+str(idx),s['title']);story.append(title)
    for b in s['blocks']:
        if b['type']=='p':story.append(para(b['text']))
        elif b['type']=='h':story.append(para(b['text'],'sub'))
        elif b['type']=='table':story.extend([make_table(b),Spacer(1,12)])
        elif b['type']=='image':
            from reportlab.lib.utils import ImageReader
            iw,ih=ImageReader(b['path']).getSize();story.append(Image(b['path'],width=width,height=width*ih/iw));story.append(Spacer(1,8));story.append(para(b['caption'],'small'))
        elif b['type']=='source':
            text=f'[{b["number"]}] '+html.escape(b['text'])+f' <link href="{html.escape(b["url"],quote=True)}" color="#16728b">打开来源</link>'
            story.append(Paragraph(text,styles['small']))
pdf=OUT/'现金接力策略_阶段性研究报告.pdf'
class ReportDoc(SimpleDocTemplate):
    def afterFlowable(self,flowable):
        if hasattr(flowable,'bookmark'):
            key,title=flowable.bookmark;self.canv.bookmarkPage(key);self.canv.addOutlineEntry(title,key,level=0)
doc=ReportDoc(str(pdf),pagesize=A4,rightMargin=right,leftMargin=left,topMargin=56,bottomMargin=49,
                     title='现金接力策略 阶段性研究报告',author='策略研究',subject='比例再平衡、双账户现金接力与PAL比较')
doc.build(story,onFirstPage=page,onLaterPages=page)
from pypdf import PdfReader
reader=PdfReader(str(pdf));texts=[p.extract_text() or '' for p in reader.pages]
assert all(len(t)>100 for t in texts)
(P/'pdf_text_check.json').write_text(json.dumps({'pages':len(texts),'page_chars':[len(t) for t in texts]},ensure_ascii=False,indent=2),encoding='utf-8')
print('PDF pages',len(texts));print(str(pdf))
