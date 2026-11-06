"""Load the exact optional local ports without importing unrelated code."""
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import sys


def load_provider(name):
    expected = json.loads(Path(__file__).with_name('providers.json').read_text(encoding='utf-8'))
    if name not in expected:
        raise ValueError(f'Unknown B provider: {name}')
    directory = os.environ.get('MORSTORM_B_LOCAL_PROVIDERS')
    path = Path(directory).expanduser().resolve()/f'{name}.py' if directory else None
    if path is None or not path.is_file():
        raise RuntimeError(f'B {name} requires a local provider. See docs/LOCAL_PROVIDERS.md and set MORSTORM_B_LOCAL_PROVIDERS.')
    source = path.read_bytes()
    if sha256(source).hexdigest() != expected[name]:
        raise RuntimeError(f'B provider checksum does not match the audited port: {path}')
    module_name = f'{__package__}.{name}'
    existing = sys.modules.get(module_name)
    if existing is not None and Path(existing.__file__) == path:
        return existing
    spec = spec_from_file_location(module_name,path)
    module = module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        exec(compile(source,str(path),'exec'),module.__dict__)
    except Exception:
        sys.modules.pop(module_name,None)
        raise
    return module
