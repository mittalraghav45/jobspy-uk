import argparse,json,logging,sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, TimeoutError
from policy import save

def search(site,query,c):
    from jobspy import scrape_jobs
    df=scrape_jobs(site_name=[site],search_term=query,location=c['location'],country_indeed='UK',results_wanted=c['results_per_query'],hours_old=c['hours_old'],fetch_description=True,description_format='plain',verbose=1)
    return json.loads(df.to_json(orient='records',date_format='iso'))

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',default='uk/config.json');p.add_argument('--out',default='results');p.add_argument('--quick',action='store_true');a=p.parse_args()
    Path(a.out).mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,handlers=[logging.StreamHandler(),logging.FileHandler(Path(a.out)/'run.log')])
    c=json.loads(Path(a.config).read_text());rows=[];errors=[]
    for site in c['sites']:
        for query in c['queries'][:1] if a.quick else c['queries']:
            logging.info('Searching %s: %s',site,query)
            pool=ProcessPoolExecutor(1)
            try:
                raw=pool.submit(search,site,query,c).result(timeout=100)
                for j in raw:
                    rows.append({'title':j.get('title'),'employer':j.get('company'),'location':j.get('location'),'salary':{'min':j.get('min_amount'),'max':j.get('max_amount'),'currency':j.get('currency'),'interval':j.get('interval')},'posting_date':j.get('date_posted'),'application_url':j.get('job_url_direct') or j.get('job_url'),'vacancy_url':j.get('job_url'),'description':j.get('description'),'source':site})
                logging.info('%s returned %s rows',site,len(raw))
            except Exception as e:
                errors.append({'site':site,'query':query,'error':str(e) or type(e).__name__});logging.exception('Search failed')
                for proc in pool._processes.values(): proc.terminate()
            finally: pool.shutdown(wait=False,cancel_futures=True)
    (Path(a.out)/'raw.json').write_text(json.dumps(rows,indent=2,default=str))
    missing=sum(not r.get('description') for r in rows)
    if missing: errors.append({'warning':f'{missing} vacancies have no description; sponsorship and exclusion checks incomplete'})
    summary=save(rows,a.out,errors);print(json.dumps(summary,indent=2))
    return 2 if not rows else 0
if __name__=='__main__':sys.exit(main())
