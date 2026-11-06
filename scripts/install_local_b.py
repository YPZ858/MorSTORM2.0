"""Extract only checksum-matched providers from an existing local 0.4.0 B package."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT/'MorSTORM-B/python/morstorm_b/native/providers.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path,help='Existing local B ZIP, wheel or extracted B source directory')
    parser.add_argument('--provider',choices=('aim','npcloud','all'),default='all')
    parser.add_argument('--target',type=Path,default=ROOT/'local_backends/b')
    args = parser.parse_args()
    entries = json.loads(LOCK.read_text(encoding='utf-8'))
    chosen = tuple(entries) if args.provider=='all' else (args.provider,)
    names = {n:f'morstorm_b/native/{n}.py' for n in chosen}
    data = {}
    if args.source.is_dir():
        for name,rel in names.items():
            data[name] = (args.source/'python'/rel).read_bytes()
    else:
        with ZipFile(args.source) as archive:
            for name,rel in names.items():
                matches = [entry for entry in archive.namelist() if entry==rel or entry.endswith('/python/'+rel)]
                if len(matches)!=1 or archive.getinfo(matches[0]).file_size>250_000:
                    raise ValueError(f'Expected one provider file for {name}.')
                data[name] = archive.read(matches[0])
    for name,source in data.items():
        if sha256(source).hexdigest()!=entries[name]:
            raise ValueError(f'{name} checksum differs from the audited provider.')
        path = args.target/f'{name}.py'
        if path.exists() and path.read_bytes()!=source:
            raise FileExistsError(f'Existing provider differs: {path}')
    args.target.mkdir(parents=True,exist_ok=True)
    for name,source in data.items():
        (args.target/f'{name}.py').write_bytes(source)
    print(f'Verified local providers: {", ".join(data)}')
    print(f'MORSTORM_B_LOCAL_PROVIDERS={args.target.resolve()}')


if __name__=='__main__':
    main()
