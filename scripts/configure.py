"""Save workstation-specific paths in the ignored settings.local.json file."""
import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fiji', dest='fiji_dir',type=Path)
    parser.add_argument('--matlab',dest='matlab_executable',type=Path)
    parser.add_argument('--author-root',type=Path)
    parser.add_argument('--b-providers',type=Path)
    parser.add_argument('--python',dest='python_executable',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'settings.local.json')
    args = vars(parser.parse_args())
    output = args.pop('output').expanduser().resolve()
    settings = json.loads(output.read_text(encoding='utf-8-sig')) if output.is_file() else {}
    for key,path in args.items():
        if path is None:
            continue
        path = path.expanduser().resolve(strict=True)
        if (key.endswith('_executable') and not path.is_file()) or (not key.endswith('_executable') and not path.is_dir()):
            raise ValueError(f'Unexpected file type for {key}: {path}')
        settings[key] = str(path)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(settings,indent=2)+'\n',encoding='utf-8')
    print(output)


if __name__=='__main__':
    main()
