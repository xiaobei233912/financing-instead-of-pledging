from pathlib import Path
import sys,zipfile,hashlib,json,shutil,runpy
from lxml import etree as E
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tmp/docx_conversion_deps'))
from opencc import OpenCC
cc=OpenCC('s2t')
src=ROOT/'output/如何在大陆通过融资执行股票质押实现买借死_简体.docx'
out=src.with_name('如何在大陸通過融資執行股票質押實現買借死_繁體.docx')
qa=ROOT/'tmp/article_variants_20260916';qa.mkdir(exist_ok=True)
backup=qa/'user_edited_original.docx'
if not backup.exists():shutil.copy2(src,backup)
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
w='{'+ns['w']+'}'
def texts(data):return E.fromstring(data).xpath('//w:t/text()',namespaces=ns)
with zipfile.ZipFile(backup) as z: parts={n:z.read(n) for n in z.namelist()}
original_text=texts(parts['word/document.xml'])
for name in ['word/styles.xml','word/document.xml']:
    root=E.fromstring(parts[name])
    for b in root.xpath('//w:pBdr',namespaces=ns):b.getparent().remove(b)
    # Suppress inherited same-style spacing collapse for consistent paragraph rhythm.
    for c in root.xpath('//w:contextualSpacing',namespaces=ns):c.set(w+'val','0')
    parts[name]=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
assert texts(parts['word/document.xml'])==original_text
def save(path,items):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for n,data in items.items():z.writestr(n,data)
save(src,parts)

# Rebuild the original data charts with the same chart code and values;
# only text glyph conversion and destination are changed.
import matplotlib
matplotlib.use('Agg')
from matplotlib.text import Text
from matplotlib.figure import Figure
old_text=Text.set_text;old_save=Figure.savefig
def trad_text(self,s):return old_text(self,cc.convert(str(s)) if s is not None else s)
def trad_save(self,path,*args,**kwargs):return old_save(self,qa/Path(path).name,*args,**kwargs)
Text.set_text=trad_text;Figure.savefig=trad_save
runpy.run_path(str(ROOT/'scripts/build_cash_relay_article_figures.py'))
Text.set_text=old_text;Figure.savefig=old_save
media_map={hashlib.sha256((ROOT/'reports/assets/cash_relay_article'/n).read_bytes()).hexdigest():qa/n for n in ['01_2000_net_assets.png','03_2009_net_assets.png']}
trad=dict(parts);converted_count=0;media_count=0
for name,data in parts.items():
    if name.startswith('word/media/'):
        h=hashlib.sha256(data).hexdigest()
        assert h in media_map, 'Unrecognized user image: '+name
        trad[name]=media_map[h].read_bytes();media_count+=1
    elif name.endswith('.xml') and (name.startswith('word/') or name=='docProps/core.xml'):
        root=E.fromstring(data)
        for p in root.xpath('//w:p',namespaces=ns):
            nodes=p.xpath('.//w:t',namespaces=ns)
            text=''.join(n.text or '' for n in nodes);converted=cc.convert(text)
            assert len(text)==len(converted), 'Conversion length changed'
            k=0
            for n in nodes:
                size=len(n.text or '');n.text=converted[k:k+size];k+=size;converted_count+=1
        for el in root.iter():
            for attr in ['descr','title']:
                if attr in el.attrib:el.set(attr,cc.convert(el.get(attr)))
            if name=='docProps/core.xml' and el.text:el.text=cc.convert(el.text)
        trad[name]=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
save(out,trad)
assert media_count==2
def paragraphs(data):
    return [''.join(p.xpath('.//w:t/text()',namespaces=ns)) for p in E.fromstring(data).xpath('//w:p',namespaces=ns)]
assert paragraphs(trad['word/document.xml'])==[cc.convert(x) for x in paragraphs(parts['word/document.xml'])]
(qa/'verification.json').write_text(json.dumps({'simplified_text_unchanged':True,'traditional_paragraph_conversion_exact':True,'images_converted':media_count,'text_nodes_converted':converted_count,'backup':str(backup),'outputs':[str(src),str(out)]},ensure_ascii=False,indent=2),encoding='utf-8')
print('Verified simplified text and traditional conversion; outputs saved.')
