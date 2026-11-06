"""Shared parameter fields and portable presets for the desktop workspace."""
from copy import deepcopy
from dataclasses import dataclass, replace
import json
import re

import runner


@dataclass(frozen=True)
class Field:
    key: str
    en: str
    zh: str
    unit: str = '—'
    kind: str = 'positive'
    optional: bool = False

    @property
    def choices(self):
        return CHOICES.get(self.kind, ())


CHOICES = {'bool': ('false', 'true'), 'flag': ('0', '1'), 'fit': ('sigma', 'sigmaxy'),
           'interp': ('linear', 'nearest', 'pchip', 'spline'), 'connect': ('4', '8')}
PIXEL = Field('camera_pixel', 'Camera pixel size', '相机像素大小', 'nm/px')
SEGMENT = Field('segment_frames', 'Frames per segment', '每段帧数', 'frames / 帧', 'int')
RENDER = Field('render_pixel', 'Render pixel size', '渲染像素大小', 'nm/px')

PICASSO_CAMERA = (
    Field('baseline', 'Camera baseline', '相机基线', 'ADU', 'nonnegative'),
    Field('sensitivity', 'Sensitivity', '相机灵敏度', 'e⁻/ADU'),
    Field('gain', 'Gain', '增益', '×'),
)
PICASSO_FIT = (
    Field('box_size', 'Fitting box side', '拟合框边长', 'px', 'odd'),
    Field('min_net_gradient', 'Minimum net gradient', '最小净梯度', 'ADU', 'nonnegative'),
    Field('fit_eps', 'Fit convergence tolerance', '拟合收敛容差'),
    Field('fit_max_it', 'Maximum fit iterations', '最大拟合迭代次数', 'iterations / 次', 'int'),
    Field('fit_method', 'Gaussian width model', '高斯宽度模型', kind='fit'),
)
PICASSO_DEFAULTS = {'fit_eps': 0.001, 'fit_max_it': 100, 'fit_method': 'sigma'}
TS_CAMERA = (
    Field('offset', 'Camera offset', '相机偏置', 'ADU', 'nonnegative'),
    Field('photons2adu', 'Photoelectrons per A/D count', '每 ADU 对应光电子数', 'e⁻/ADU'),
    Field('isemgain', 'Enable EM gain', '启用 EM 增益', kind='bool', optional=True),
    Field('gainem', 'EM gain factor', 'EM 增益倍数', '×', optional=True),
    Field('readoutnoise', 'Readout noise', '读出噪声', 'e⁻', 'nonnegative', True),
    Field('quantumefficiency', 'Quantum efficiency', '量子效率', '0–1', 'fraction', True),
)
TS_ANALYSIS = (
    Field('filter', 'Filter', '滤波器', kind='text', optional=True),
    Field('scale', 'Wavelet scale', '小波尺度', 'px', optional=True),
    Field('order', 'Wavelet order', '小波阶数', kind='int', optional=True),
    Field('detector', 'Detector', '检测器', kind='text', optional=True),
    Field('connectivity', 'Detector neighborhood', '检测器邻域', kind='text', optional=True),
    Field('threshold', 'Detection threshold expression', '检测阈值表达式', 'macro / 宏', 'text', True),
    Field('estimator', 'PSF estimator', 'PSF 估计器', kind='text', optional=True),
    Field('sigma', 'Initial PSF sigma', 'PSF 初始 sigma', 'px', optional=True),
    Field('fitradius', 'Fitting radius', '拟合半径', 'px', 'int', True),
    Field('method', 'Fitting method', '拟合方法', kind='text', optional=True),
    Field('full_image_fitting', 'Fit full image', '拟合整幅图像', kind='bool', optional=True),
    Field('mfaenabled', 'Enable multi-emitter fitting', '启用多发射体拟合', kind='bool', optional=True),
    Field('renderer', 'ThunderSTORM renderer', 'ThunderSTORM 渲染器', kind='text', optional=True),
)
TS_EXTRAS = (
    Field('extra_camera', 'Other camera macro options', '其他相机宏参数', 'macro / 宏', 'macro', True),
    Field('extra_analysis', 'Other analysis macro options', '其他分析宏参数', 'macro / 宏', 'macro', True),
)
MEANSHIFT = (
    Field('nTimeBin', 'Time bins', '时间箱数', 'bins / 箱', 'bins'),
    Field('rmax', 'Pair search radius', '配对搜索半径', 'nm'),
    Field('maxiter', 'Maximum iterations', '最大迭代次数', 'iterations / 次', 'int'),
    Field('calc_error', 'Estimate errors and weight pairs', '估计误差并对配对加权', kind='flag'),
    Field('broadsweep', 'Enable broad sweep', '启用宽搜索', kind='flag'),
    Field('delta_broad', 'Broad sweep width', '宽搜索窗口', 'nm'),
    Field('delta_narrow_ratio', 'Narrow sweep ratio', '窄搜索比例', '×'),
    Field('interp_method', 'Drift interpolation', '漂移插值方式', kind='interp'),
    Field('outlier_error', 'Outlier residual threshold', '离群残差阈值', 'nm', 'nonnegative'),
)
MEANSHIFT_DEFAULTS = dict(zip((f.key for f in MEANSHIFT), (20, 500, 200, 1, 0, 100, 3, 'linear', 50)))
NPCLOUD = (
    SEGMENT,
    Field('MaxSearchRadius_Pix1', 'Pass 1 XY search radius', '第一遍 XY 搜索半径', 'camera px / 相机 px'),
    Field('MaxSearchRadius_Pix2', 'Pass 2 XY search radius', '第二遍 XY 搜索半径', 'camera px / 相机 px'),
    Field('ReSampleFold', 'Resampling factor', '重采样系数', '×'),
    Field('TolZnm', 'Pass 1 Z tolerance (3D)', '第一遍 Z 容差（3D）', 'nm'),
    Field('TolZnm2', 'Pass 2 Z tolerance (3D)', '第二遍 Z 容差（3D）', 'nm'),
)
MORPHOLOGY = (
    RENDER,
    Field('sigma_px', 'Gaussian smoothing sigma', '高斯平滑 sigma', 'render px / 渲染 px', 'nonnegative'),
    Field('threshold', 'Smoothed density threshold', '平滑后密度阈值', 'counts/px / 计数每像素'),
    Field('connectivity', 'Connectivity', '连通性', 'neighbors / 邻域', 'connect'),
    Field('min_area_nm2', 'Minimum object area', '最小对象面积', 'nm²', 'nonnegative'),
    Field('exclude_border', 'Exclude border objects', '排除接触边缘的对象', kind='bool'),
)
FIELDS = {'Picasso': (PIXEL, *PICASSO_CAMERA, *PICASSO_FIT),
          'ThunderSTORM': (PIXEL, *TS_CAMERA, *TS_ANALYSIS, *TS_EXTRAS),
          'meanshift': MEANSHIFT, 'npcloud': NPCLOUD, 'rrnpcloud': NPCLOUD,
          'aim': (SEGMENT,), 'morphology': MORPHOLOGY}

FIXED = {
    'Picasso': ('Fixed: upstream 2D MLE and Qe = 1 (metadata only).', '固定：原版 2D MLE，Qe = 1（仅元数据）。'),
    'ThunderSTORM': ('Fixed: localization export to CSV. Blank options are omitted from the ImageJ macro.',
                     '固定：定位结果导出为 CSV。空白选项不传给 ImageJ 宏。'),
    'meanshift': ('Fixed: author time bin construction and drift origin. Flags use 0 = off, 1 = on.',
                  '固定：作者的时间分箱方式和漂移参考原点。标志位 0 为关闭，1 为开启。'),
    'npcloud': ('Fixed: report the author’s first pass. The author routine also computes pass 2.',
                '固定：输出作者算法第一遍结果。作者例程还会计算第二遍。'),
    'rrnpcloud': ('Fixed: report the author’s combined result after pass 2.', '固定：输出作者算法第二遍完成后的合并结果。'),
    'aim': ('Fixed: intersection distance 20 nm and local search radius 60 nm. The last localized frame must divide into at least two complete segments.',
            '固定：相交距离 20 nm，局部搜索半径 60 nm。最后一个定位帧的帧号须能分成至少两个完整段。'),
    'morphology': ('Fixed: XY density projection, Gaussian smoothing, then connected components in MorphoLibJ.',
                   '固定：在 XY 平面渲染密度，经高斯平滑后使用 MorphoLibJ 识别连通对象。'),
}

MACRO_TOKEN = re.compile(r'([\w.-]+)(?:=(?:\[([^\[\]\r\n]*)\]|([^\s\[\]]+)))?(?=\s|$)')


def macro_options(text):
    if not isinstance(text, str) or '\n' in text or '\r' in text:
        raise ValueError('ImageJ macro options must occupy one line.')
    tokens = {}
    rest = text.strip()
    while rest:
        match = MACRO_TOKEN.match(rest)
        if match is None:
            raise ValueError(f'Invalid ImageJ macro option near {rest[:40]!r}.')
        key, bracketed, plain = match.groups()
        key = key.lower()
        if key in tokens:
            raise ValueError(f'Duplicate ImageJ macro option: {key}.')
        tokens[key] = bracketed if bracketed is not None else plain
        rest = rest[match.end():].lstrip()
    return tokens


def macro_text(options):
    parts = []
    for key, value in options.items():
        if value is None:
            parts.append(key)
        else:
            value = display(value)
            if any(char in value for char in '[]\r\n'):
                raise ValueError(f'{key} contains an invalid ImageJ macro character.')
            parts.append(f'{key}=[{value}]' if any(char.isspace() for char in value) or not value else f'{key}={value}')
    return ' '.join(parts)


def display(value):
    if isinstance(value, bool):
        return str(value).lower()
    return '' if value is None else str(value)


def parse_field(field, value):
    text = display(value).strip()
    if not text and field.optional:
        return None
    if field.choices:
        if text not in field.choices:
            raise ValueError(f'{field.en}: choose {", ".join(field.choices)}.')
        if field.kind == 'bool':
            return text == 'true'
        return int(text) if field.kind in ('flag', 'connect') else text
    if field.kind in ('text', 'macro'):
        if not text or '\n' in text or '\r' in text:
            raise ValueError(f'{field.en}: enter a single line.')
        return text
    value = runner.number(text, field.en, integer=field.kind in ('int', 'bins', 'odd'),
                          minimum={'bins': 2, 'odd': 3}.get(field.kind, 0),
                          inclusive=field.kind in ('nonnegative', 'bins', 'odd', 'fraction'))
    if field.kind == 'odd' and value % 2 == 0:
        raise ValueError('The Picasso fitting box side must be odd.')
    if field.kind == 'fraction' and value > 1:
        raise ValueError(f'{field.en} must be between 0 and 1.')
    return value


def fields_from_macros(localization):
    result = {}
    for key, fields, extra in zip(('camera_options', 'analysis_options'), (TS_CAMERA, TS_ANALYSIS), TS_EXTRAS):
        options = macro_options(localization[key])
        if key == 'camera_options':
            options.pop('pixelsize', None)
        for field in fields:
            if field.key in options:
                option = options.pop(field.key)
                result[field.key] = 'true' if option is None and field.kind == 'bool' else option
        result[extra.key] = macro_text(options)
    return result


def values(config, panel):
    if panel == 'Picasso':
        loc = config['localization']
        return {'camera_pixel': config['input']['pixel_size_nm'], **loc['camera'],
                'box_size': loc['box_size'], 'min_net_gradient': loc['min_net_gradient'],
                **{key: loc.get(key, default) for key, default in PICASSO_DEFAULTS.items()}}
    if panel == 'ThunderSTORM':
        return {'camera_pixel': config['input']['pixel_size_nm'], **fields_from_macros(config['localization'])}
    if panel == 'morphology':
        return {'render_pixel': config['render']['pixel_size_nm'], 'exclude_border': False, **config['morphology']}
    drift = config['drift']
    options = drift.get('parameters', {})
    if panel == 'meanshift':
        return {**MEANSHIFT_DEFAULTS, **options.get('meanshift', {})}
    if panel in ('npcloud', 'rrnpcloud'):
        return {'segment_frames': drift['segment_frames'], 'TolZnm': 110, 'TolZnm2': 90, **options.get('npcloud', {})}
    return {'segment_frames': drift['segment_frames']}


def set_values(config, panel, incoming):
    parsed = {field.key: parse_field(field, incoming.get(field.key)) for field in FIELDS[panel]}
    if panel in runner.BACKENDS:
        config['input']['pixel_size_nm'] = parsed.pop('camera_pixel')
        loc = config['localization']
        if panel == 'Picasso':
            loc['camera'] = {field.key: parsed.pop(field.key) for field in PICASSO_CAMERA}
            loc.update(parsed)
        else:
            for key, fields, extra in zip(('camera_options', 'analysis_options'), (TS_CAMERA, TS_ANALYSIS), TS_EXTRAS):
                options = {f.key: parsed[f.key] for f in fields if parsed[f.key] is not None}
                extensions = macro_options(parsed[extra.key] or '')
                reserved = {field.key for field in fields} | ({'pixelsize'} if key == 'camera_options' else set())
                if reserved.intersection(extensions):
                    raise ValueError('Set named ThunderSTORM options in their dedicated fields.')
                loc[key] = macro_text({**options, **extensions})
    elif panel == 'morphology':
        config['render']['pixel_size_nm'] = parsed.pop('render_pixel')
        config['morphology'].update(parsed)
    else:
        drift = config['drift']
        if 'segment_frames' in parsed:
            drift['segment_frames'] = parsed.pop('segment_frames')
        if panel != 'aim':
            drift['parameters']['meanshift' if panel == 'meanshift' else 'npcloud'] = parsed


def section_key(panel, backend):
    return (panel, backend) if panel in runner.METHODS.values() else (panel,)


def export_preset(profile, modules, pixel, period, render):
    all_stages = runner.MODULES if profile.mode == 'raw' else runner.MODULES[1:]
    config = runner.configured_profile(profile, all_stages, pixel, period, None, render)
    config['modules'] = list(modules)
    config['input']['path'] = ''
    config['output_dir'] = 'results/morstorm-preset'
    config['drift'].pop('official', None)
    config['morphology']['enabled'] = 'morphology' in modules
    config['morphology'].pop('fiji_dir', None)
    config.pop('local_b_provider_dir', None)
    if profile.mode == 'raw':
        for key in ('fiji_dir', 'python_executable'):
            config['localization'].pop(key, None)
    return config


def import_preset(path, backend_hint):
    """Load a schema-1 profile or a saved run without adopting local paths or an engine."""
    config = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(config, dict) or config.get('schema_version', 1) != 1:
        raise ValueError('Select a MorSTORM schema-1 JSON preset.')
    try:
        inp = config['input']
        mode = {'movie': 'raw', 'localizations': 'cached'}[inp['kind']]
        method = config['drift']['method'].lower()
        backend = config.get('parameter_preset') or config.get('localization', {}).get('backend')
        if backend is None:
            backend = {'thunderstorm': 'ThunderSTORM', 'picasso': 'Picasso'}.get(inp.get('format'), backend_hint)
        backend = next((item for item in runner.BACKENDS if item.lower() == backend.lower()), None)
        profile = runner.load_profile(mode, backend, method)
        stages = runner.MODULES if mode == 'raw' else runner.MODULES[1:]
        legacy_stages = [stage for stage in stages if stage != 'morphology' or config.get('morphology', {}).get('enabled', True)]
        selected = config.get('modules', legacy_stages)
        if not isinstance(selected, list) or not selected or any(stage not in stages for stage in selected):
            raise ValueError('The preset stages do not match its input type.')
        if mode == 'raw' and 'localize' not in selected:
            raise ValueError('The preset stages do not match its input type.')
        incoming = deepcopy(profile.config)
        incoming['input'].update(inp)
        for key in ('localization', 'render', 'morphology'):
            if key in config:
                incoming.setdefault(key, {}).update(config[key])
        source_drift = config['drift']
        incoming['drift'].update(source_drift)
        opts = source_drift.get('parameters', {})
        if method == 'meanshift':
            extras = {**source_drift.get('official_options', {}), **opts.get('meanshift', {})}
            if 'nTimeBin' in source_drift:
                extras['nTimeBin'] = source_drift['nTimeBin']
            if set(extras) - set(MEANSHIFT_DEFAULTS):
                raise ValueError('The preset contains an unsupported MeanShift option.')
            incoming['drift']['parameters'] = {'meanshift': {**profile.config['drift']['parameters']['meanshift'], **extras}}
        elif method in ('npcloud', 'rrnpcloud'):
            extras = opts.get('npcloud', {})
            if set(extras) - {field.key for field in NPCLOUD[1:]}:
                raise ValueError('The preset contains an unsupported NP-Cloud option.')
            defaults = profile.config['drift']['parameters']['npcloud'].copy()
            if 'radius_nm' in source_drift:
                px = runner.number(inp.get('pixel_size_nm'), 'Camera pixel size')
                radius = runner.number(source_drift['radius_nm'], 'Search radius') / px
                defaults.update(MaxSearchRadius_Pix1=radius, MaxSearchRadius_Pix2=0.75*radius)
            incoming['drift']['parameters'] = {'npcloud': {**defaults, **extras}}
        elif opts.get('aim') or source_drift.get('intersect_nm', 20) != 20 or source_drift.get('radius_nm', 60) != 60:
            raise ValueError('AIM intersection distance and search radius are fixed by the author.')

        panels = (backend, method, 'morphology') if mode == 'raw' else (method, 'morphology')
        resolved = deepcopy(profile.config)
        resolved['input']['pixel_size_nm'] = runner.number(incoming['input']['pixel_size_nm'], 'Camera pixel size')
        for panel in panels:
            set_values(resolved, panel, values(incoming, panel))
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError('The file is missing a required MorSTORM preset field or has an invalid value.') from error
    return replace(profile, config=resolved), tuple(stage for stage in stages if stage in selected)
