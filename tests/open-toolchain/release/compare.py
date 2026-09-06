"""Compare validated SC64 update payloads and list exact differing byte intervals.

Matching copied reference bytes is not a source rebuild. This tool only measures
identity; the caller must establish where each candidate component came from.
"""
import argparse
import json
from pathlib import Path

from release_update import inspect


def differences(left,right):
    runs=[];start=None
    for index in range(max(len(left),len(right))):
        changed=index>=len(left) or index>=len(right) or left[index]!=right[index]
        if changed and start is None:
            start=index
        if not changed and start is not None:
            runs.append([start,index]);start=None
    if start is not None:
        runs.append([start,max(len(left),len(right))])
    return runs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference',type=Path);parser.add_argument('candidate',type=Path)
    args=parser.parse_args();left=args.reference.read_bytes();right=args.candidate.read_bytes()
    a={c['id']:c for c in inspect(left)};b={c['id']:c for c in inspect(right)}
    result={'files_identical':left==right,'file_differing_intervals':differences(left,right),'components':{}}
    for ident in sorted(a.keys()|b.keys()):
        if ident not in a or ident not in b:
            result['components'][ident]={'missing':'reference' if ident not in a else 'candidate'}
            continue
        aa,bb=a[ident],b[ident]
        ap=left[aa['payload_offset']:aa['payload_offset']+aa['length']]
        bp=right[bb['payload_offset']:bb['payload_offset']+bb['length']]
        result['components'][ident]={'identical':ap==bp,'reference_sha256':aa['sha256'],
            'candidate_sha256':bb['sha256'],'payload_differing_intervals':differences(ap,bp)}
    print(json.dumps(result,indent=2))
    return 0 if left==right else 1


if __name__=='__main__':
    raise SystemExit(main())
