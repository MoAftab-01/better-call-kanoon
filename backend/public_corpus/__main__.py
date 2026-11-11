import argparse
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description='Prepare an unpublished candidate or inspect it offline. Never approves.')
    sub=p.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--output',type=Path,required=True)
    inspect=sub.add_parser('inspect');inspect.add_argument('--directory',type=Path,required=True)
    inspect.add_argument('--sha256',required=True);inspect.add_argument('--query')
    measurement=sub.add_parser('measure');measurement.add_argument('--directory',type=Path,required=True)
    measurement.add_argument('--sha256',required=True);measurement.add_argument('--query',default='BNS section 15')
    args=p.parse_args()
    if args.command=='prepare':
        from .prepare import prepare
        result=prepare(Path(__file__).resolve().parents[2],args.output)
    elif args.command=='measure':
        from .measure import measure
        result=measure(args.directory,args.sha256,args.query)
    else:
        from .runtime import PublicIndex
        index=PublicIndex(args.directory,args.sha256,preview=True)
        result=index.status()
        if args.query:
            result['hits']=[dict(reference=h.identifier,title=h.source.title,source_url=h.source.source_url,
                physical_page=h.page.physical_page,lines=[h.record.start_line,h.record.end_line]) for h in index.search(args.query)]
        if not index.passages:
            print(json.dumps(result));return 2
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0


if __name__=='__main__':raise SystemExit(main())
