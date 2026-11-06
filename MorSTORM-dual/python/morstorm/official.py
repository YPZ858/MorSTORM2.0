"""Run original author MATLAB code through the shared MATLAB dispatcher.

No algorithm is reimplemented in Python. MATLAB is an explicit runtime dependency
for author-code methods; missing/changed sources raise errors without fallbacks.
"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import numpy as np
from scipy.io import savemat, loadmat


def _paths():
    package = Path(__file__).resolve().parent
    bundled = package / 'resources'
    if (bundled / 'matlab/+morstorm/official_drift.m').is_file():
        return bundled / 'matlab', bundled / 'official_sources.lock.json', Path.cwd() / 'third_party'
    project = package.parents[1]
    return project / 'matlab', project / 'shared/official_sources.lock.json', project / 'third_party'


def estimate_author(table, config):
    cfg = dict(config)
    official = dict(cfg.get('official', {}))
    matlab_code, lock, default_deps = _paths()
    official.setdefault('root', os.environ.get('MORSTORM_THIRD_PARTY', str(default_deps)))
    official.setdefault('lock_file', str(lock))
    for key in ('root','lock_file','meanshift_dir','npcloud_dir','aim_dir'):
        if key in official: official[key] = str(Path(official[key]).resolve())
    executable = official.get('matlab_executable') or os.environ.get('MORSTORM_MATLAB') or shutil.which('matlab')
    if not executable:
        raise RuntimeError('Author methods require MATLAB. Set drift.official.matlab_executable or MORSTORM_MATLAB.')
    cfg['official'] = official
    job_parent = Path(cfg.pop('_run_dir', official.get('work_dir', Path.cwd() / 'work/morstorm-jobs'))).resolve()
    job_parent.mkdir(parents=True, exist_ok=True)
    job = Path(tempfile.mkdtemp(prefix=cfg['method'] + '-', dir=job_parent))
    axes = [a for a in ('x_nm','y_nm','z_nm') if a in table]
    data = table[['frame'] + axes].to_numpy(dtype=float)
    savemat(job / 'input.mat', {'localizations': data}, do_compression=False)
    (job / 'config.json').write_text(json.dumps(cfg, indent=2), encoding='utf-8')
    env = os.environ.copy()
    env['MORSTORM_MATLAB_CODE'] = str(matlab_code)
    env['MORSTORM_DRIFT_JOB'] = str(job)
    expression = "addpath(getenv('MORSTORM_MATLAB_CODE')); morstorm.drift_job(getenv('MORSTORM_DRIFT_JOB'));"
    with (job / 'matlab.log').open('w', encoding='utf-8') as log:
        try:
            completed = subprocess.run([str(executable), '-batch', expression], env=env,
                                       stdout=log, stderr=subprocess.STDOUT,
                                       timeout=official.get('timeout_seconds', 600), check=False)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f'Author MATLAB job timed out; see {job / "matlab.log"}') from error
    if completed.returncode or not (job / 'output.mat').is_file():
        detail = ''
        if (job / 'error.json').is_file():
            detail = json.loads((job / 'error.json').read_text(encoding='utf-8-sig')).get('message','')
        raise RuntimeError(f'Author MATLAB job failed: {detail}; see {job / "matlab.log"}')
    curve = np.asarray(loadmat(job / 'output.mat')['curve'], dtype=float)
    diagnostics = json.loads((job / 'diagnostics.json').read_text(encoding='utf-8-sig'))
    diagnostics['frontend'] = 'python -> author MATLAB code'
    diagnostics['matlab_job_directory'] = str(job)
    return curve, diagnostics
