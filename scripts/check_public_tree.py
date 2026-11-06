"""Reject local datasets, optional providers and workstation data in a release tree."""
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
IGNORED = {'.git','.venv','__pycache__','.numba_cache','build','dist','results','third_party','local_backends'}
TEXT = {'.py','.m','.json','.md','.txt','.toml','.yml','.yaml','.cff','.cmd','.ps1','.java','.ijm','.in'}
PRIVATE = re.compile(r'[a-z]:[/\\]+users[/\\]|[/\\]home[/\\](?!path)|X\d+Y\d+R\d+W\d+C\d+_\d+|gh[pousr]_[a-z0-9]{20,}|AKIA[A-Z0-9]{16}',re.I)


def candidates():
    if (ROOT/'.git').exists():
        result = subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT)
        return [ROOT/name for name in result.decode('utf-8').split('\0') if name]
    return [path for path in ROOT.rglob('*') if path.is_file()
            and not IGNORED.intersection(path.relative_to(ROOT).parts)
            and not any(part.endswith('.egg-info') for part in path.relative_to(ROOT).parts)]


def main():
    files = candidates()
    problems = []
    for path in files:
        rel = path.relative_to(ROOT)
        ext = path.suffix.lower()
        if (IGNORED.intersection(rel.parts) or path.name.endswith('.local.json') or
            ext in ('.tif','.tiff','.h5','.hdf5','.mat','.zip','.whl','.pdf','.log') or ext.startswith('.mex') or
            path.name in ('aim.py','npcloud.py','CBSPcodeV2.m','published_2d.npz')):
            problems.append(f'Non-release file: {rel}')
        elif path.is_symlink() or path.stat().st_size>2_000_000:
            problems.append(f'Unexpected large file or symlink: {rel}')
        elif ext in TEXT and PRIVATE.search(path.read_text(encoding='utf-8-sig')):
            problems.append(f'Workstation or credential pattern: {rel}')
    if problems:
        raise SystemExit('\n'.join(problems))
    print(f'Public tree check passed ({len(files)} files).')


if __name__=='__main__':
    main()
