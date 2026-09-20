from pathlib import Path
import hashlib,json,re,os,shutil
from urllib.parse import unquote
R=Path(__file__).resolve().parent.parent
A=R/'Archive'
B=R/'tmp/archive_20260920_before'
assert not A.exists(), 'Archive already exists; inspect before rerun'
keep={'README.md','现金接力_部分融资规则更新.md','现金接力部分融资_逐年账_relay70.md','现金接力部分融资_逐年账_relay80.md','现金接力部分融资_逐年账_relay70_w3.md'}
files=[p for p in (R/'reports').iterdir() if p.is_file() and p.name not in keep]
files+=list((R/'docs').rglob('*'))+list((R/'doubao_audit').rglob('*'))
files+=[p for p in (R/'output').rglob('*') if p.is_file() and p.suffix.lower()!='.docx']
files=[p for p in files if p.is_file()]
# Images used by the final articles stay in their established location.
mapping={p.resolve():A/p.relative_to(R) for p in files}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before={str(p.relative_to(R)):digest(p) for p in files}
for p in [R/'README.md',R/'reports/README.md',*files]:
    q=B/p.relative_to(R);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
def relocate_target(t,old,new):
    if t.startswith(('http:','https:','mailto:','data:','#')):return t
    path,sep,frag=t.partition('#');path=unquote(path)
    isabs=bool(re.match(r'^[A-Za-z]:[/\\]',path))
    target=Path(path).resolve() if isabs else (old.parent/path).resolve()
    if not target.is_relative_to(R):return t
    dest=mapping.get(target,target)
    # Directory references, chiefly the complete external audit copy.
    if target.is_relative_to(R/'doubao_audit'):
        dest=A/target.relative_to(R)
    if dest==target and old.parent==new.parent:return t
    value=dest.as_posix() if isabs else Path(os.path.relpath(dest,new.parent)).as_posix()
    return value+(sep+frag if sep else '')
md=re.compile(r'(\]\()([^\n)]*)(\))')
html=re.compile(r'((?:src|href)=[\"\'])([^\"\']+)([\"\'])')
changed=[]
for p,q in mapping.items():
    assert q.resolve().is_relative_to(A.resolve()) and p.is_relative_to(R)
    q.parent.mkdir(parents=True,exist_ok=True)
    # Verified workspace-local destinations; no deletes or shell-composed moves.
    shutil.move(str(p),str(q))
    if q.suffix in ('.md','.html'):
        s=q.read_text(encoding='utf-8-sig');pattern=md if q.suffix=='.md' else html
        out=pattern.sub(lambda m:m[1]+relocate_target(m[2],p,q)+m[3],s)
        if out!=s:q.write_text(out,encoding='utf-8');changed.append(str(q.relative_to(R)))
        assert pattern.sub(lambda m:m[1]+m[3],out)==pattern.sub(lambda m:m[1]+m[3],s)

latest='现金接力_部分融资规则更新.md'
ledger=['现金接力部分融资_逐年账_relay70.md','现金接力部分融资_逐年账_relay80.md','现金接力部分融资_逐年账_relay70_w3.md']
word=list((R/'output').glob('*.docx'))
root=['# 现金接力研究工作区','', '整理日期：2026-09-20。外层只保留当前报告与最终文章；历史资料集中在 Archive，不能沿用其中旧规则或数值。','',
'## 当前研究依据','',f'- [部分融资规则更新](reports/{latest})：当前规则、回测参数、压力测试及卖资产/PAL对照。',
'- [逐年双账户明细](reports/README.md)：70/30提取2%、80/20提取2%、70/30提取3%。',
'- 当前数据：[results/partial_living_cash1_rate3](results/partial_living_cash1_rate3/)。行情截止2026-09-08；归档日期不是数据更新日期。','',
'## 当前口径','',
'现金年收益1%；接力融资3%单利挂息，不主动还本付息。允许部分融资、先转后借，先支付生活费再比例再平衡；融资买回后允许低于300%。70/30与80/20买股现金底线分别为初始资产30%与20%，只限制买股，生活费及补担保可动用。160%触发现金类证券补担保、目标200%；140%为研究停止线。PAL对照为80/20年度再平衡、每年借初始资产2%、3%复利。具体执行约束与审核时点以当前报告的说明为准。','',
'70/30提取2%和80/20提取2%完成当前2000年主回测；70/30提取3%发生生活费支付失败。历史通过不等于未来保证。','',
'## 最终文章','']
root += [f'- [{p.stem}](output/{p.name})' for p in word]
root += ['', '最终文章保留作者手动修改；研究参数及数值核对以当前研究报告和配套账表为依据。旧Markdown源稿、旧PDF和续写草稿已归档。','',
'## 目录分工','', '| 目录 | 用途 |','| --- | --- |',
'| reports/ | 当前回测报告、逐年账及配图 |','| output/ | 最终简体、繁体Word |',
'| Archive/ | 旧报告、模型说明、展示稿、外部审计；仅供追溯 |',
'| data/ | 原始行情与数据审计，保持原位 |','| results/ | 当前及历史结果并存；仅上方指定目录是当前主要结果 |',
'| scripts/ | 当前和历史复现程序并存；运行旧生成器可能重新生成旧报告，不能按新生成时间认定为当前 |',
'| reference/ | 原参考项目 |','| tmp/ | 工作备份与排版检查等中间文件，不是正式成果 |','',
'[历史归档索引](Archive/README.md) · [迁移清单](Archive/migration_manifest.json)','']
(R/'README.md').write_text('\n'.join(root),encoding='utf-8')
report=['# 当前研究报告','',f'- [部分融资规则更新]({latest})：现金1%、接力融资3%单利，PAL 3%复利；先转后借、允许部分融资，先生活费后再平衡。','']
report += [f'- [{p[:-3]}]({p})' for p in ledger]
report+=['','旧参数对照、失败配置和压力测试是当前报告的一部分，保留其明确标注的适用范围。','',
'最终文章见[工作区导航](../README.md)。早期报告和文章草稿见[历史归档](../Archive/README.md)。','']
(R/'reports/README.md').write_text('\n'.join(report),encoding='utf-8')
index=['# 历史归档','', '本目录保留策略演进、旧参数结果及写作过程材料，不作为当前执行规则。当前依据见[工作区导航](../README.md)。','',
'早期报告可能采用按月付息、双向暂停再平衡、尚无补担保、全额或零融资、操作后300%、现金2%/融资2.8%等不同口径。保留原文和原数值；仅修正链接。','',
'阶段性报告与PPT即使包含160%/200%规则，也不代表已纳入最新部分融资及利率设定。文章源稿、续写稿及旧PDF已被作者修订后的Word取代。','',
'数据和主程序仍在工作区原位置；历史报告链接已调整。doubao_audit整套审计副本一并归档，内部程序与数据相对结构保持不变。','',
'## 文件索引','']
records=[]
for p,q in mapping.items():
    rel=str(p.relative_to(R));new=q.relative_to(A).as_posix()
    reason=('历史外部审计副本' if rel.startswith('doubao_audit') else '旧模型或研究任务及PPT文案' if rel.startswith('docs') else '已被最终Word替代的源稿或旧展示成品' if rel.startswith('output') else '被当前规则报告或最终文章替代的历史报告')
    records.append(dict(original=rel,destination=str(q.relative_to(R)),reason=reason,sha256_before=before[rel],sha256_after=digest(q),link_only_edit=str(q.relative_to(R)) in changed))
    if q.suffix.lower() in ('.md','.pdf','.pptx','.html'):index.append(f'- [{new}]({new})：{reason}。')
    assert not p.exists()
    if not records[-1]['link_only_edit']:assert digest(q)==before[rel]
(A/'README.md').write_text('\n'.join(index)+'\n',encoding='utf-8')
(A/'migration_manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'moved_files':len(records),'link_only_updates':len(changed),'backup':str(B)},ensure_ascii=True))
