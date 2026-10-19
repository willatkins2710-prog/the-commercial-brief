#!/usr/bin/env python3
"""Refresh UK/global sector news and monthly World Bank commodity benchmarks."""
import concurrent.futures, datetime as dt, email.utils, hashlib, html, io, json, re, sys
import urllib.parse, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from quick_summaries import enrich_summaries, fpa_feature_stories

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'/'news.json'
NOW=dt.datetime.now(dt.timezone.utc)
QUERIES={
'supermarkets':{'UK':'(Morrisons OR Tesco OR Sainsbury OR Asda OR Aldi OR Lidl) supermarkets business when:7d','Global':'(Walmart OR Costco OR Kroger OR Carrefour) grocery business when:7d'},
'ai':{'UK':'AI artificial intelligence UK business regulation investment when:7d','Global':'OpenAI Anthropic Google Microsoft Nvidia AI technology when:7d'},
'economy':{'UK':'UK inflation interest rates economy Bank of England GDP when:7d','Global':'global economy inflation Fed IMF GDP when:7d'},
'retail':{'UK':'UK retail high street consumers spending sales when:7d','Global':'world retail ecommerce consumers shopping sales when:7d'},
'commercial-finance':{'UK':['commercial finance business partnering pricing promotions profitability UK when:14d','FP&A budgeting forecasts management accountants decision making UK when:14d'],'Global':['FP&A revenue growth management accounting forecasting insights when:14d','CFO finance business partnering profit margin commercial strategy when:14d']},
'finance':{'UK':'UK banking stock market corporate finance earnings when:7d','Global':'US markets Wall Street banking earnings mergers when:7d'},
'food':{'UK':'UK food manufacturing agriculture ingredients prices when:7d','Global':'global food agriculture crops meat cocoa wheat prices when:7d'},
'energy':{'UK':'UK fuel power gas electricity energy prices when:7d','Global':'oil brent natural gas global energy shipping when:7d'},
'supply':{'UK':'UK logistics transport packaging freight supply chains when:7d','Global':'global shipping logistics trade tariffs supply chains when:7d'},
'commodities':{'UK':['UK food commodities beef dairy wheat cocoa eggs wholesale market prices when:14d','UK bird flu livestock disease animal disease crop drought harvest food supply when:14d','UK food ingredient shortages weather supply shocks farm yields when:14d'],'Global':['global cocoa coffee sugar wheat dairy commodity supply demand prices when:14d','global crop drought floods harvest disease supply shock food trade when:14d','global livestock bird flu avian influenza food commodity outbreak when:14d']}}
RSS_FEEDS=[
    ('supermarkets','UK','The Grocer','https://www.thegrocer.co.uk/34272.rss',''),
    ('commercial-finance','Global','CFO Dive','https://www.cfodive.com/feeds/news/','commercial'),
    ('commodities','UK','The Grocer','https://www.thegrocer.co.uk/34272.rss','commodities'),
    ('economy','UK','BBC News','https://feeds.bbci.co.uk/news/business/rss.xml',''),
]
COMMODITY_WORDS=re.compile(
    r'\b(beef|cattle|pork|pigs|chicken|poultry|avian|bird flu|livestock|sheep|lamb|'
    r'dairy|milk|cheese|butter|wheat|grain|flour|eggs|sugar|cocoa|coffee|food supply|'
    r'harvest|crop|drought|flood|disease|outbreak|weather|shortage|farm|agricultur|'
    r'feedstock|palm oil|commodity|commodities|soybean|packaging)\b',re.I)
FINANCE_WORDS=re.compile(
    r'\b(CFO|finance|FP&A|forecast|budget|planning|profit|pricing|margin|cost|'
    r'accounting|revenue|business partner|strategy|efficiency|commercial|'
    r'cash flow|operating model|transformation|automation)\b',re.I)
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



COMMODITY_PRODUCT=re.compile(
    r'\b(beef|cattle|pork|pig|chicken|poultry|livestock|sheep|lamb|meat|'
    r'dairy|milk|cheese|butter|wheat|grain|flour|egg|sugar|cocoa|coffee|'
    r'crop|harvest|food commodit|food ingredient|rice|palm oil|soybean|'
    r'potato|fish|seafood|farm|animal feed|produce)\w*\b',re.I)
COMMODITY_SIGNAL=re.compile(
    r'\b(supply|shortage|cost|price|inflation|tight|drought|disease|outbreak|'
    r'avian|bird flu|weather|elnino|el niño|la niña|yield|harvest|forecast|'
    r'risk|regulation|tariff|production|quarantine|future|expect|pressure|'
    r'collapse|flood|heatwave|heat wave|disruption)\w*\b',re.I)
FINANCE_RELEVANCE=re.compile(
    r'\b(FP&A|forecast|budget|planning|pricing|promotion|margin|profit|'
    r'revenue management|revenue growth|commercial finance|business partner|'
    r'financial strategy|finance transformation|financial model|'
    r'working capital|return on investment|ROI|analytics|cost reduction|'
    r'capital allocation|scenario|CFO survey|finance team)\w*\b',re.I)
FINANCE_NOISE=re.compile(
    r'\b(appoints?|appointed|named CFO|new CFO|CFO out|leaves|resigns?|'
    r'indicted|arrested|court|trial|leadership shuffle|mortgage|'
    r'company secretary|lease accounting|bookkeeping)\b',re.I)


def story_is_relevant(article):
    title=article.get('title','')
    if article.get('section')=='commercial-finance':
        if article.get('source')=='FP&A Trends':
            return True
        return bool(FINANCE_RELEVANCE.search(title)) and not FINANCE_NOISE.search(title)
    if article.get('section')=='commodities':
        if re.search(r'\b(seabird|wild bird|captive bird|pet food|hunger aid|'
                     r'food security monitor|wildlife|conservation)\b',title,re.I):
            return False
        return bool(COMMODITY_PRODUCT.search(title) and COMMODITY_SIGNAL.search(title))
    return True

def publisher_stories(section,region,publisher,url,filter_name):
    try:
        root=ET.fromstring(download(url,timeout=18))
        out=[]
        for item in root.findall('./channel/item')[:35]:
            title=clean(item.findtext('title'))
            link=clean(item.findtext('link'))
            desc=clean(item.findtext('description'))
            published=pubdate(clean(item.findtext('pubDate')))
            if not published or not title or not link.startswith('https://'):
                continue
            if NOW-published>dt.timedelta(days=30) or published>NOW+dt.timedelta(days=1):
                continue
            target=title+' '+desc[:200]
            if filter_name=='commodities' and not COMMODITY_WORDS.search(target):
                continue
            if filter_name=='commercial' and not FINANCE_WORDS.search(target):
                continue
            ident=hashlib.sha1((title.casefold()+publisher.casefold()).encode()).hexdigest()[:16]
            out.append({
                'id':ident,'title':title,'description':desc[:260],
                'preview':desc[:1800],'url':link,'source':publisher,
                'region':region,'section':section,'published':published.isoformat(),
                'direct_source':True
            })
            if len(out)>=18:break
        print('Publisher RSS',publisher,section,len(out))
        return out
    except Exception as exc:
        print('Publisher feed unavailable:',publisher,str(exc)[:150],file=sys.stderr)
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
    jobs=[(sector,region,query) for sector,regions in QUERIES.items() for region,queries in regions.items() for query in (queries if isinstance(queries,list) else [queries])]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        publisher_groups=list(pool.map(lambda args:publisher_stories(*args),RSS_FEEDS))
        groups=list(pool.map(lambda args:stories(*args),jobs))
    found=[a for group in publisher_groups+groups for a in group]
    found.extend(fpa_feature_stories())
    found=[a for a in found if story_is_relevant(a)]
    unique={}
    for article in sorted(found,key=lambda a:a['published'],reverse=True):
        fingerprint=re.sub(r'\W+','',article['title'].casefold())[:140]
        if fingerprint not in unique:unique[fingerprint]=article
    all_unique=list(unique.values())
    # Reserve space for every desk, especially commercial finance and commodities.
    quotas={section:(24 if section in ('commercial-finance','commodities') else 14)
            for section in QUERIES}
    fresh=[]
    selected_ids=set()
    for section in QUERIES:
        candidates=[a for a in all_unique if a['section']==section]
        # Include publisher-first coverage to make source-grounded summaries available.
        direct=[a for a in candidates if a.get('direct_source')]
        reserve=min(6,len(direct),quotas[section])
        for a in direct[:reserve]:
            if a['id'] not in selected_ids:
                fresh.append(a); selected_ids.add(a['id'])
        for a in sorted(candidates,key=lambda v:v['published'],reverse=True):
            if sum(x['section']==section for x in fresh)>=quotas[section]:
                break
            if a['id'] not in selected_ids:
                fresh.append(a); selected_ids.add(a['id'])
    fresh=sorted(fresh,key=lambda a:a['published'],reverse=True)[:160]
    if len(fresh)<12:
        existing={a['id'] for a in fresh}
        fresh.extend(a for a in old.get('articles',[]) if a.get('id') not in existing and a.get('published','') >= (NOW-dt.timedelta(days=30)).isoformat())
    fresh=enrich_summaries(fresh,old.get('articles',[]))
    previous=old.get('prices',{})
    prices=monthly_prices(previous)
    output={'updated_at':NOW.isoformat() if found else old.get('updated_at'),
        'price_updated_at':NOW.isoformat() if prices is not previous else old.get('price_updated_at'),
        'articles':fresh[:160],'prices':prices,'feeds_succeeded':sum(bool(g) for g in publisher_groups+groups)}
    DATA.parent.mkdir(exist_ok=True,parents=True)
    DATA.write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Updated',len(output['articles']),'stories;',len(prices),'commodity benchmarks')

if __name__=='__main__':main()
