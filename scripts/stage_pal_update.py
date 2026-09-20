"""User specified PAL: 80/20, 2% initial spending, 3% effective compound interest."""
from stage_research import *
rows=load_rows();end=rows[-1]['date'];main=[];rolling=[]
for name in ['pal80','pal80_hold']:
    for start in ['2000-03-27','2009-03-09','2007-10-31','2020-02-19','2021-11-19']:
        r,y,d,e=dispatch(rows,name,start,end);r.update(name=name);main.append(r)
        save(name+'_'+start+'_annual.json',y);save(name+'_'+start+'_daily.json',d)
    starts={}
    for row in rows:
        day=dt.date.fromisoformat(row['date']);starts.setdefault((day.year,(day.month-1)//3),day)
    for years in [10,20]:
        for day in starts.values():
            stop=dt.date(day.year+years,day.month,day.day)-dt.timedelta(days=1)
            if str(stop)>end:continue
            r,_,_,_=dispatch(rows,name,str(day),str(stop));r.update(name=name,years=years);rolling.append(r)
save('pal_main.json',main);save('pal_rolling.json',rolling)
print('PAL update complete',len(main),len(rolling))
