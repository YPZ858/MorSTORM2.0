"""Prepare a GUI job and dispatch it to an existing MorSTORM entry point."""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'results' / 'gui'
PROFILES = ROOT / 'profiles'
A = ROOT / 'MorSTORM-dual'
B = ROOT / 'MorSTORM-B'
ENGINES = ('B Python', 'A Python', 'A MATLAB')
METHODS = {'AIM': 'aim', 'MeanShift': 'meanshift', 'NP-Cloud': 'npcloud', 'RR-NP Cloud': 'rrnpcloud'}
BACKENDS = ('ThunderSTORM', 'Picasso')


@dataclass(frozen=True)
class Profile:
    mode: str
    backend: str
    method: str
    config: dict

    @property
    def source(self):
        path = self.config['input']['path']
        return Path(path) if path else None

    @property
    def period(self):
        drift = self.config['drift']
        return drift['parameters']['meanshift']['nTimeBin'] if self.method == 'meanshift' else drift['segment_frames']


def local_settings():
    path = Path(os.environ.get('MORSTORM_SETTINGS', ROOT/'settings.local.json')).expanduser().resolve()
    settings = json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else {}
    for key, variable in (('fiji_dir','MORSTORM_FIJI'),('matlab_executable','MORSTORM_MATLAB'),
                          ('author_root','MORSTORM_THIRD_PARTY'),('b_providers','MORSTORM_B_LOCAL_PROVIDERS')):
        if os.environ.get(variable):
            settings[key] = os.environ[variable]
    for key in ('fiji_dir','matlab_executable','author_root','b_providers','python_executable'):
        if settings.get(key):
            settings[key] = str((path.parent/Path(settings[key]).expanduser()).resolve())
    return settings


def load_profile(mode, backend, method):
    if mode not in ('raw', 'cached') or backend not in BACKENDS or method not in METHODS.values():
        raise ValueError('Select a supported input, localization backend and drift method.')
    path = PROFILES / mode / f'{backend.lower()}-{method}.json'
    config = json.loads(path.read_text(encoding='utf-8-sig'))
    for section, key in (('input', 'path'), ('morphology', 'fiji_dir'), ('localization', 'fiji_dir')):
        if config.get(section, {}).get(key):
            config[section][key] = str((path.parent / config[section][key]).resolve())
    official = config['drift']['official']
    official['root'] = str((path.parent / official['root']).resolve())
    settings = local_settings()
    official['root'] = settings.get('author_root',official['root'])
    official['matlab_executable'] = settings.get('matlab_executable') or shutil.which('matlab') or 'matlab'
    config['morphology']['fiji_dir'] = settings.get('fiji_dir','')
    config['local_b_provider_dir'] = settings.get('b_providers',str(ROOT/'local_backends/b'))
    if mode=='raw':
        if backend=='ThunderSTORM':
            config['localization']['fiji_dir'] = config['morphology']['fiji_dir']
        else:
            python = Path(sys.executable)
            if python.name.lower()=='pythonw.exe':
                python = python.with_name('python.exe')
            config['localization']['python_executable'] = settings.get('python_executable',str(python))
    return Profile(mode, backend, method, config)


def camera_values(profile):
    if profile.mode == 'cached':
        return {}
    loc = profile.config['localization']
    if profile.backend == 'Picasso':
        return {**loc['camera'], 'box_size': loc['box_size'], 'min_net_gradient': loc['min_net_gradient']}
    return {
        'offset': float(re.search(r'\boffset=([^ ]+)', loc['camera_options']).group(1)),
        'photons2adu': float(re.search(r'\bphotons2adu=([^ ]+)', loc['camera_options']).group(1)),
        'threshold_sigma': float(re.search(r'\bthreshold=([\d.]+)\*std\(Wave.F1\)', loc['analysis_options']).group(1)),
    }


def number(value, label, *, minimum=0, integer=False, inclusive=False):
    try:
        converted = float(value)
    except (ValueError, TypeError) as error:
        raise ValueError(f'{label} must be numeric.') from error
    invalid_range = converted < minimum if inclusive else converted <= minimum
    if not math.isfinite(converted) or invalid_range or (integer and not converted.is_integer()):
        relation = 'at least' if inclusive else 'greater than'
        unit = 'an integer' if integer else 'a number'
        raise ValueError(f'{label} must be {unit} {relation} {minimum:g}.')
    return int(converted) if integer else converted


def parse_camera(profile, values):
    expected = camera_values(profile)
    if set(values) != set(expected):
        raise ValueError('The camera settings do not match the selected localizer.')
    result = {}
    for key, value in values.items():
        result[key] = number(value, key, integer=key == 'box_size',
                             minimum=3 if key == 'box_size' else 0,
                             inclusive=key in ('baseline', 'offset', 'box_size'))
    if 'box_size' in result and result['box_size'] % 2 == 0:
        raise ValueError('The Picasso fitting box must be odd.')
    return result


MODULES = ('localize','drift','morphology')
RAW_EXT = {'.tif','.tiff'}
TABLE_EXT = {'.csv','.hdf5','.h5'}
ARTIFACTS = {'drift': ('drift.csv','corrected.csv'),
             'morphology': ('density.tif','labels.tif','morphology.csv','assignments.csv')}


@dataclass(frozen=True)
class Job:
    engine: str
    source: Path
    folder_mode: bool
    modules: tuple
    config: dict
    output: Path


def make_job(profile, engine, source, folder_mode, modules, output_base, pixel, period, camera, render_pixel):
    modules = tuple(stage for stage in MODULES if stage in modules)
    if not modules or engine not in ENGINES or not source.strip() or not output_base.strip():
        raise ValueError('Select an engine, at least one module, an input and a result directory.')
    raw = 'localize' in modules
    if raw != (profile.mode=='raw'):
        raise ValueError('The profile input mode does not match the selected modules.')
    cfg = deepcopy(profile.config)
    pixel = number(pixel,'Camera pixel size')
    cfg['input']['pixel_size_nm'] = pixel
    cfg['drift']['pixel_size_nm'] = pixel
    if 'drift' in modules:
        period = number(period,'Time bins' if profile.method=='meanshift' else 'Frames per segment',integer=True)
        if profile.method=='meanshift':
            cfg['drift']['parameters']['meanshift']['nTimeBin'] = period
        else:
            cfg['drift']['segment_frames'] = period
    if 'morphology' in modules:
        cfg['render']['pixel_size_nm'] = number(render_pixel,'Render pixel size')
    if raw:
        camera = parse_camera(profile,camera)
        loc = cfg['localization']
        loc['pixel_size_nm'] = pixel
        if profile.backend=='Picasso':
            loc['camera'] = {k:camera[k] for k in ('baseline','sensitivity','gain')}
            loc.update(box_size=camera['box_size'],min_net_gradient=camera['min_net_gradient'])
        else:
            for key,value in (('offset',camera['offset']),('photons2adu',camera['photons2adu']),('pixelsize',pixel)):
                loc['camera_options'] = re.sub(rf'\b{key}=[^ ]+',f'{key}={value:g}',loc['camera_options'])
            loc['analysis_options'] = re.sub(r'\bthreshold=[\d.]+\*std\(Wave.F1\)',
                f'threshold={camera["threshold_sigma"]:g}*std(Wave.F1)',loc['analysis_options'])
    token = datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:6]
    output = Path(output_base).expanduser().resolve()/f'morstorm-{token}'
    cfg['modules'] = list(modules)
    cfg['execution_engine'] = engine
    return Job(engine,Path(source).expanduser().resolve(),folder_mode,modules,cfg,output)


def inputs(job):
    valid_ext = RAW_EXT if 'localize' in job.modules else TABLE_EXT
    if job.folder_mode:
        if not job.source.is_dir():
            raise FileNotFoundError(f'Input folder not found: {job.source}')
        paths = sorted((p for p in job.source.iterdir() if p.is_file() and p.suffix.lower() in valid_ext),
                       key=lambda p:(p.name.casefold(),p.name))
        if not paths:
            raise ValueError('The folder contains no matching input files at its top level.')
        return paths
    if not job.source.is_file() or job.source.suffix.lower() not in valid_ext:
        raise ValueError(f'Select an existing input with one of these extensions: {", ".join(sorted(valid_ext))}.')
    return [job.source]


def file_config(job, source, folder):
    config = deepcopy(job.config)
    pixel = config['input']['pixel_size_nm']
    if 'localize' in job.modules:
        inp = {'kind':'movie','path':str(source),'pixel_size_nm':pixel}
    else:
        inp = {'kind':'localizations','path':str(source),'pixel_size_nm':pixel,
               'format':'csv' if source.suffix.lower()=='.csv' else 'picasso',
               'coordinate_unit':'nm','frame_base':1}
    config.update(input=inp, output_dir=str(folder))
    return config


def check_dependencies(job):
    cfg = job.config
    project = B if job.engine=='B Python' else A
    if not (project/'python').is_dir():
        raise FileNotFoundError(f'MorSTORM source not found: {project}')
    if job.engine=='A MATLAB' or (job.engine=='A Python' and 'drift' in job.modules):
        official = cfg['drift']['official']
        if not Path(official['matlab_executable']).is_file():
            raise FileNotFoundError('Variant A needs its configured MATLAB executable.')
        if 'drift' in job.modules and not Path(official['root']).is_dir():
            raise FileNotFoundError('Variant A drift needs the pinned author source directory.')
    if job.engine=='B Python' and 'drift' in job.modules and cfg['drift']['method']!='meanshift':
        name = 'aim' if cfg['drift']['method']=='aim' else 'npcloud'
        if not (Path(cfg['local_b_provider_dir'])/f'{name}.py').is_file():
            raise FileNotFoundError(f'B {name} needs a local provider. See docs/LOCAL_PROVIDERS.md or select A.')

    def fiji_check(settings, morphology):
        if not settings.get('fiji_dir'):
            raise ValueError('Configure the Fiji path with scripts/configure.py before starting this module.')
        fiji = Path(settings['fiji_dir'])
        plugin = 'MorphoLibJ_*.jar' if morphology else '*Thunder*STORM*.jar'
        if not any((fiji/'jars').glob('ij-*.jar')) or not any(fiji.rglob(plugin)):
            raise FileNotFoundError(f'Fiji or {plugin} is missing: {fiji}')
        if not (project/'shared/morstorm-morphology.jar').is_file():
            raise FileNotFoundError(f'MorSTORM Java bridge is missing: {project}')
        explicit = settings.get('java_executable')
        found = Path(explicit).is_file() or shutil.which(explicit) if explicit else (
            any((fiji/'java').glob('**/bin/java.exe')) or shutil.which('java'))
        if not found:
            raise FileNotFoundError(f'Java is missing for {fiji}.')

    if 'morphology' in job.modules:
        fiji_check(cfg['morphology'],True)
    if 'localize' in job.modules:
        loc = cfg['localization']
        if loc['backend']=='thunderstorm':
            fiji_check(loc,False)
        elif job.engine=='A MATLAB':
            if not Path(loc['python_executable']).is_file():
                raise FileNotFoundError('The configured Picasso Python executable is missing.')
        else:
            from importlib.util import find_spec
            if find_spec('picasso') is None:
                raise ImportError('Picasso is missing in this Python environment.')


def check_picasso_parts(source):
    """Avoid silently joining TIFF parts and processing them again in folder mode."""
    name = source.name
    suffix = '.ome.tif' if name.lower().endswith('.ome.tif') else '.tif' if 'NDTiffStack' in name else None
    if not suffix:
        return
    base = name[:-len(suffix)]
    part = re.fullmatch(r'(.+)_\d+',base)
    names = [p.name for p in source.parent.iterdir() if p.is_file()]
    companion = re.compile(re.escape(base)+r'_\d+'+re.escape(suffix)+r'$',re.IGNORECASE)
    if any(companion.fullmatch(n) for n in names) or (part and (part[1]+suffix).casefold() in {n.casefold() for n in names}):
        raise ValueError('Picasso split TIFF series detected. Export each acquisition as one TIFF stack before using this workspace.')


def inspect_input(config):
    import numpy as np
    source = Path(config['input']['path'])
    occupied = None
    if 'localize' in config['modules']:
        import tifffile
        if config['localization']['backend']=='picasso':
            check_picasso_parts(source)
        with tifffile.TiffFile(source) as tif:
            series = tif.series[0]
            if len(tif.series)!=1 or series.axes not in ('TYX','ZYX','IYX','QYX'):
                raise ValueError('Select a single-channel TIFF stack of 2D frames.')
            frame_count = int(series.shape[0])
    else:
        if str(B/'python') not in sys.path:
            sys.path.insert(0,str(B/'python'))
        from morstorm_b.io import read_localizations
        table = read_localizations(source,config['input']).table
        frame_count = int(table.frame.max())
        occupied = np.sort(table.frame.unique())
    if 'drift' not in config['modules']:
        return frame_count
    if occupied is not None and occupied[0]!=1:
        raise ValueError('Drift correction requires the first localized frame to be frame 1.')

    drift = config['drift']
    method,segment = drift['method'],drift['segment_frames']
    if method=='meanshift':
        bins = drift['parameters']['meanshift']['nTimeBin']
        if not 2<=bins<=frame_count:
            raise ValueError(f'MeanShift time bins must be between 2 and {frame_count}.')
        width = frame_count//bins
        starts = np.floor(1+np.arange(bins)*(frame_count-width)/(bins-1)+.5).astype(int)
        stops = starts+width
    else:
        if method=='aim':
            count,remainder = divmod(frame_count,segment)
            if remainder or count<2:
                raise ValueError(f'AIM needs at least two complete segments. {frame_count} frames are incompatible with {segment} frames per segment.')
        else:
            count = math.floor((frame_count-1)/segment+.5)
            centers = math.floor((frame_count-(segment+1)/2)/segment)+1
            fold = drift['parameters']['npcloud']['ReSampleFold']
            if count<2 or count!=centers or math.floor(count/fold+.5)<1:
                raise ValueError(f'NP-Cloud segment or resampling limits are unmet: {frame_count} frames, {segment} frames per segment, fold {fold}.')
        starts = 1+np.arange(count)*segment
        stops = starts+segment
    if occupied is not None:
        empty = np.flatnonzero(np.searchsorted(occupied,starts)==np.searchsorted(occupied,stops))
        if len(empty):
            raise ValueError(f'Segment {int(empty[0])+1} contains no localizations.')
    return frame_count


def command(job, config_path):
    env = os.environ.copy()
    env.update(PYTHONUTF8='1',PYTHONUNBUFFERED='1')
    project = B if job.engine=='B Python' else A
    env['PYTHONPATH'] = os.pathsep.join(filter(None,(str(project/'python'),env.get('PYTHONPATH'))))
    if job.engine=='B Python':
        env['MORSTORM_B_LOCAL_PROVIDERS'] = job.config['local_b_provider_dir']
    if 'localize' in job.modules and job.config['localization']['backend']=='thunderstorm':
        env.setdefault('JAVA_TOOL_OPTIONS','-Xmx10g')
    gui = Path(__file__).resolve().parent
    if job.engine=='A MATLAB':
        env.update(MORSTORM_GUI_CONFIG=str(config_path),MORSTORM_GUI_MATLAB=str(A/'matlab'),MORSTORM_GUI_CODE=str(gui))
        expr = "addpath(getenv('MORSTORM_GUI_MATLAB')); addpath(getenv('MORSTORM_GUI_CODE')); morstorm_gui_stages(getenv('MORSTORM_GUI_CONFIG'));"
        return [job.config['drift']['official']['matlab_executable'],'-batch',expr],env
    python = Path(sys.executable)
    if python.name.lower()=='pythonw.exe':
        python = python.with_name('python.exe')
    package = 'morstorm_b' if job.engine=='B Python' else 'morstorm'
    return [str(python),'-u',str(gui/'worker.py'),package,str(config_path)],env


def save_json(path, value):
    temporary = path.with_name(f'.{path.name}.tmp')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    temporary.replace(path)


def fingerprint(source):
    digest = sha256()
    with source.open('rb') as file:
        for block in iter(lambda:file.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def run_item(job, source, folder, notify):
    config = file_config(job,source,folder)
    config_path = folder/'run-config.json'
    save_json(config_path,config)
    frames = inspect_input(config)
    notify('inspection',frames)
    source_hash = fingerprint(source)
    args,env = command(job,config_path)
    last = ''
    with (folder/'console.log').open('w',encoding='utf-8') as log:
        with subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
                              encoding='utf-8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)) as child:
            for line in child.stdout:
                log.write(line)
                log.flush()
                if line.startswith('::morstorm-stage::'):
                    notify('stage',line.strip().split('::')[-1])
                else:
                    notify('log',line)
                    if line.strip():
                        last = line.strip()
            code = child.wait()
    if code:
        raise RuntimeError(f'Exit code {code}. {last}')
    result = json.loads((folder/'stage-result.json').read_text(encoding='utf-8-sig'))
    required = [name for stage in job.modules for name in ARTIFACTS.get(stage,())]
    if 'localize' in job.modules:
        required.append(result['localization']['output'])
    if any(not (folder/name).is_file() for name in required):
        raise RuntimeError('The selected modules did not produce all expected artifacts.')
    return {**result,'input_sha256':source_hash}


def run(job, notify):
    """Run each file in isolation and save a progress ledger in the job folder."""
    try:
        paths = inputs(job)
        check_dependencies(job)
        job.output.mkdir(parents=True,exist_ok=False)
        report = {'engine':job.engine,'modules':list(job.modules),'input':str(job.source),
                  'input_mode':'folder' if job.folder_mode else 'file','status':'running','total':len(paths),'files':[]}
        report_path = job.output/'batch-report.json'
        save_json(report_path,report)
        notify('batch_start',len(paths))
        for index,source in enumerate(paths,1):
            stem = re.sub(r'[^\w.-]+','_',source.stem).strip('._')[:56] or 'input'
            folder = job.output/f'{index:03d}-{stem}'
            folder.mkdir()
            item = {'source':str(source),'output':folder.name,'status':'running'}
            report['files'].append(item)
            save_json(report_path,report)
            notify('file',(index,len(paths),source.name,folder))
            try:
                result = run_item(job,source,folder,notify)
                item.update(status='complete',localizations=result['localizations'],last_frame=result['last_frame'])
                save_json(folder/'manifest.json',{**item,**result,'modules':list(job.modules),'engine':job.engine})
            except Exception as error:
                item.update(status='failed',error=str(error))
                save_json(folder/'manifest.json',{**item,'modules':list(job.modules),'engine':job.engine})
            save_json(report_path,report)
            notify('file_done',item.copy())
        report['completed'] = sum(item['status']=='complete' for item in report['files'])
        report['failed'] = len(paths)-report['completed']
        report['status'] = 'complete' if not report['failed'] else 'completed_with_failures'
        save_json(report_path,report)
        notify('complete',report)
    except Exception as error:
        notify('error',str(error))
