#!/usr/bin/env python3
"""Refresh UK/global sector news and monthly World Bank commodity benchmarks."""
import concurrent.futures, datetime as dt, email.utils, hashlib, html, io, json, re, sys
import urllib.parse, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'/'news.json'
NOW=dt.datetime.now(dt.timezone.utc)
QUERIES={
'supermarkets':{'UK':'(Morrisons OR Tesco OR Sainsbury OR Asda OR Aldi OR Lidl) supermarkets business when:7d','Global':'(Walmart OR Costco OR Kroger OR Carrefour) grocery business when:7d'},
'ai':{'UK':'AI artificial intelligence UK business regulation investment when:7d','Global':'OpenAI Anthropic Google Microsoft Nvidia AI technology when:7d'},
'economy':{'UK':'UK inflation interest rates economy Bank of England GDP when:7d','Global':'global economy inflation Fed IMF GDP when:7d'},
'retail':{'UK':'UK retail high street consumers spending sales when:7d','Global':'world retail ecommerce consumers shopping sales when:7d'},
'finance':{'UK':'UK banking stock market corporate finance earnings when:7d','Global':'US markets Wall Street banking earnings mergers when:7d'},
'food':{'UK':'UK food manufacturing agriculture ingredients prices when:7d','Global':'global food agriculture crops meat cocoa wheat prices when:7d'},
'energy':{'UK':'UK fuel power gas electricity energy prices when:7d','Global':'oil brent natural gas global energy shipping when:7d'},
'supply':{'UK':'UK logistics transport packaging freight supply chains when:7d','Global':'global shipping logistics trade tariffs supply chains when:7d'},
'commodities':{'UK':'UK beef pork chicken dairy eggs wholesale prices AHDB when:7d','Global':'cocoa sugar wheat oil beef commodities market when:7d'}}
WB='https://thedocs.worldbank.org/en/doc/5d903e848db1d1b83e0ec8f744e55570-0350012021/related/CMO-Historical-Data-Monthly.xlsx'
MARKETS={'oil':('crude oil, brent','$/bbl'),'beef':('beef','$/kg'),'wheat':('wheat, us hrw','$/mt'),'cocoa':('cocoa','$/kg'),'sugar':('sugar, world','$/kg'),'gas':('natural gas (europe)','$/mmbtu'),'palm':('palm oil','$/mt')}

def download(url,timeout=20):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 CommercialBrief/1.0'})
    with urllib.request.urlopen(req,timeout=timeout) as response:return response.read()

def clean(value):return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',value or ''))).strip()

def pubdate(value):
    try:return email.utils.parsedate_to_datetime(value).astimezone(dt.timezone.utc)
    except:return None

def stories(section,region,query):
    params=urllib.parse.urlencode({'q':query,'hl':'en-GB','gl':'GB' if region=='UK' else 'US','ceid':'GB:en' if region=='UK' else 'US:en'})
    try:
        root=ET.fromstring(download('https://news.google.com/rss/search?'+params))
        out=[]
        for item in root.findall('./channel/item')[:16]:
            title=clean(item.findtext('title'));link=clean(item.findtext('link'))
            source=clean(item.findtext('source')) or 'Google News'
            published=pubdate(clean(item.findtext('pubDate')))
            if not published or not title or not link.startswith('http'):continue
            if NOW-published>dt.timedelta(days=30) or published>NOW+dt.timedelta(days=1):continue
            if title.endswith(' - '+source):title=title[:-(len(source)+3)]
            ident=hashlib.sha1((title.casefold()+source.casefold()).encode()).hexdigest()[:16]
            out.append({'id':ident,'title':title,'description':clean(item.findtext('description'))[:240],
                        'url':link,'source':source,'region':region,'section':section,'published':published.isoformat()})
        print(section,region,len(out))
        return out
    except Exception as exc:
        print('Feed unavailable:',section,region,str(exc)[:150],file=sys.stderr)
        return []

def monthly_prices(previous):
    try:
        import openpyxl
        wb=openpyxl.load_workbook(io.BytesIO(download(WB,timeout=35)),read_only=True,data_only=True)
        ws=next((s for s in wb.worksheets if 'monthly' in s.title.casefold()),wb.worksheets[0])
        rows=list(ws.values)
        headers=[(sum(any(label in str(cell or '').casefold() for label,_ in MARKETS.values()) for cell in row),i) for i,row in enumerate(rows[:20])]
        score,header_index=max(headers)
        if score<3:raise ValueError('Monthly price header not found')
        labels=[str(v or '').casefold().strip() for v in rows[header_index]]
        output={}
        for key,(label,unit) in MARKETS.items():
            ix=next((i for i,v in enumerate(labels) if v==label),None)
            if ix is None:continue
            series=[]
            for row in rows[header_index+1:]:
                if len(row)<=ix or not isinstance(row[ix],(int,float)) or row[ix]<=0:continue
                d=row[0]
                if isinstance(d,(dt.date,dt.datetime)):period=d.strftime('%Y-%m')
                else:
                    match=re.match(r'(20\d{2})[-M](\d\d)',str(d).strip())
                    period=f'{match.group(1)}-{match.group(2)}' if match else None
                if period and period<=NOW.strftime('%Y-%m'):series.append((period,float(row[ix])))
            series.sort()
            if len(series)<13:continue
            series=series[-18:]
            latest,prior,lastyear=series[-1][1],series[-2][1],series[-13][1]
            output[key]={'latest':round(latest,3),'mom':round((latest/prior-1)*100,1),
                'yoy':round((latest/lastyear-1)*100,1),
                'date':dt.datetime.strptime(series[-1][0],'%Y-%m').strftime('%b %Y'),
                'series':[round(v,4) for _,v in series[-12:]],'source':'World Bank Pink Sheet','unit':unit}
        if not output:raise ValueError('No valid monthly price series')
        return output
    except Exception as exc:
        print('Price update unavailable; retaining dated observations:',str(exc)[:200],file=sys.stderr)
        return previous

def main():
    try:old=json.loads(DATA.read_text(encoding='utf-8'))
    except Exception:old={'articles':[],'prices':{}}
    jobs=[(sector,region,query) for sector,regions in QUERIES.items() for region,query in regions.items()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        groups=list(pool.map(lambda j:stories(*j),jobs))
    found=[a for group in groups for a in group]
    unique={}
    for article in sorted(found,key=lambda a:a['published'],reverse=True):
        fingerprint=re.sub(r'\W+','',article['title'].casefold())[:140]
        if fingerprint not in unique:unique[fingerprint]=article
    fresh=list(unique.values())
    if len(fresh)<12:
        existing={a['id'] for a in fresh}
        fresh.extend(a for a in old.get('articles',[]) if a.get('id') not in existing and a.get('published','') >= (NOW-dt.timedelta(days=30)).isoformat())
    previous=old.get('prices',{})
    prices=monthly_prices(previous)
    output={'updated_at':NOW.isoformat() if found else old.get('updated_at'),
        'price_updated_at':NOW.isoformat() if prices is not previous else old.get('price_updated_at'),
        'articles':fresh[:160],'prices':prices,'feeds_succeeded':sum(bool(g) for g in groups)}
    DATA.parent.mkdir(exist_ok=True,parents=True)
    DATA.write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Updated',len(output['articles']),'stories;',len(prices),'commodity benchmarks')

if __name__=='__main__':main()
