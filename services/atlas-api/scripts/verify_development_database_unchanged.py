import argparse,json
from pathlib import Path
from sqlalchemy import create_engine,text
QUERIES={"sites":"atlas.sites","site_profiles":"atlas.site_profiles","site_versions":"atlas.site_versions","site_geometries":"atlas.site_geometries","quality_snapshots":"atlas.site_quality_snapshots","merge_proposals":"staging.merge_proposals","execution_batches":"staging.merge_execution_batches","execution_items":"staging.merge_execution_items","execution_events":"audit.merge_execution_events","promotion_records":"staging.promotion_records","publication_records":"atlas.publication_records"}
def snapshot(url):
    with create_engine(url).connect() as c:return {k:c.scalar(text(f"SELECT count(*) FROM {v}")) for k,v in QUERIES.items()}
def main():
    p=argparse.ArgumentParser();p.add_argument("--url",required=True);p.add_argument("--before");p.add_argument("--output",required=True);a=p.parse_args();now=snapshot(a.url);before=json.loads(Path(a.before).read_text()) if a.before else now;result={"before":before,"after":now,"unchanged":before==now};Path(a.output).parent.mkdir(parents=True,exist_ok=True);Path(a.output).write_text(json.dumps(result,indent=2),encoding="utf-8");raise SystemExit(0 if result["unchanged"] else 1)
if __name__=="__main__":main()
