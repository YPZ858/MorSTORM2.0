"""Run native post-fitting and reconstruction on an existing localization table."""
import base64
from importlib import import_module
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

import numpy as np


def thunderstorm(pipeline, source, config, output, operations=(), reconstruction=False):
    locs = pipeline.read_localizations(source['path'], source)
    table = locs.table.copy()
    # The native CSV importer understands ThunderSTORM names and units.
    table.rename(columns={axis: f'{axis[0]} [nm]' for axis in locs.axes}, inplace=True)
    if 'id' not in table:
        table.insert(0, 'id', np.arange(1, len(table) + 1))
    supported = re.compile(r'^(id|frame|[xyz]|sigma[12]?|intensity|uncertainty(?:_z)?|offset|bkgstd|chi2|detections)(?: \[[^\]]+\])?$')
    needed = {'id', 'frame', 'x [nm]', 'y [nm]', 'z [nm]'}
    columns = [name for name in table if name in needed or (not reconstruction and supported.fullmatch(name))]
    labels = {name.split(' [')[0] for name in columns}
    merging = any(op.startswith('action=merge ') for op in operations)
    if merging and 'uncertainty' in labels:
        has_sigma = 'sigma' in labels or {'sigma1', 'sigma2'} <= labels
        if not has_sigma or not {'intensity', 'bkgstd'} <= labels:
            raise ValueError('ThunderSTORM Merge needs sigma, intensity and background deviation (bkgstd) to recalculate uncertainty. Export the complete fitting table.')
        if 'localize' not in config.get('modules', ()) and not {'intensity [photon]', 'bkgstd [photon]'} <= set(columns):
            raise ValueError('Export intensity and bkgstd in photons before merging a table with uncertainty.')
    if any(op.startswith('action=duplicates ') for op in operations) and 'uncertainty' not in labels:
        raise ValueError('ThunderSTORM Remove duplicates requires the fitting uncertainty column.')
    if any(op.startswith('action=density ') and 'dimensions=3D' in op for op in operations) and 'z' not in labels:
        raise ValueError('ThunderSTORM 3D density filtering requires a Z column.')
    staged = output / ('reconstruction-input.csv' if reconstruction else 'postfit-input.csv')
    table[columns].to_csv(staged, index=False, float_format='%.17g', na_rep='NaN')
    exported = output / 'postfit.csv'
    image = output / 'thunderstorm-reconstruction.tif'
    fiji = Path(config['morphology']['fiji_dir'])
    bridge = import_module(f'{pipeline.__package__}.bridge')
    ij = sorted((fiji / 'jars').glob('ij-*.jar'), key=bridge._version)[-1]
    plugin = next(p for p in sorted((fiji / 'plugins').glob('*.jar')) if re.search(r'thunder.*storm', p.name, re.I))
    candidates = sorted((fiji / 'java').glob('**/bin/java.exe' if os.name == 'nt' else '**/bin/java'))
    java = str(candidates[-1]) if candidates else 'java'
    cp = os.pathsep.join(map(str, (bridge.resource('morstorm-morphology.jar'), ij, plugin, fiji / 'jars' / '*')))
    pixel = source['pixel_size_nm']
    render = config.get('reconstruction', {})
    magnification = pixel / render.get('pixel_size_nm', 10)
    renderer = render.get('renderer', 'Histograms')
    # Explicit manual bounds preserve negative or drift-shifted coordinates.
    xy = locs.table[['x_nm', 'y_nm']].to_numpy() / pixel
    left, top = np.floor(xy.min(axis=0) - 1)
    width, height = np.ceil(xy.max(axis=0) + 1) - [left, top]
    if reconstruction and math.ceil(width*magnification)*math.ceil(height*magnification) > 100_000_000:
        raise ValueError('ThunderSTORM reconstruction is too large. Increase the reconstruction pixel size.')
    render_options = (f'autosize=manual imleft={left:g} imtop={top:g} imwidth={width:g} imheight={height:g} '
                      f'renderer=[{renderer}] magnification={magnification:.17g} shifts={render.get("averages", 2)} avg=0 '
                      f'threeD=false colorizeZ=false')
    exports = ' '.join(f'{name.split(" [")[0]}=true' for name in columns)
    if merging and 'detections' not in labels:
        exports += ' detections=true'
    settings = output / ('reconstruction-settings.txt' if reconstruction else 'postfit-settings.txt')
    camera = config.get('localization', {}).get('camera_options')
    if not camera:
        camera = f'pixelsize={pixel:.17g} isemgain=false photons2adu=1 offset=0'
    lines = [staged.as_posix(), '-' if reconstruction else exported.as_posix(),
             image.as_posix() if reconstruction else '-',
             camera, exports, render_options, *operations]
    if any(any(char in line for char in '\r\n') for line in lines):
        raise ValueError('ThunderSTORM options must each occupy one line.')
    if any(char in staged.as_posix() + exported.as_posix() for char in '[]'):
        raise ValueError('ThunderSTORM macro paths cannot contain square brackets.')
    settings.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    macro = Path(__file__).with_name('thunderstorm_table.ijm')
    encoded = [base64.b64encode(str(path).encode()).decode() for path in (macro, settings)]
    log_path = settings.with_suffix('.log')
    try:
        with log_path.open('w', encoding='utf-8') as log:
            subprocess.run([java, '-Djava.awt.headless=false', '-Dfile.encoding=UTF-8', f'-Dplugins.dir={fiji}',
                            '-cp', cp, 'MorstormThunderstorm', '--base64', *encoded], check=True,
                           stdout=log, stderr=subprocess.STDOUT, timeout=3600)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f'ThunderSTORM table operation failed; see {log_path.name}.') from error
    target = image if reconstruction else exported
    marker = settings.with_suffix('.txt.done')
    finished = marker.is_file() and marker.read_text(encoding='utf-8') == 'complete'
    if not finished or not target.is_file() or not target.stat().st_size:
        raise RuntimeError(f'ThunderSTORM did not write {target.name}; see {log_path.name}.')
    if reconstruction:
        return source, {'output': image.name, 'pixel_size_nm': render.get('pixel_size_nm', 10),
                        'origin_nm': [float(left*pixel), float(top*pixel)], 'renderer': renderer}
    result = {'path': str(exported), 'format': 'thunderstorm', 'coordinate_unit': 'nm',
              'frame_base': 1, 'pixel_size_nm': pixel}
    count = len(pipeline.read_localizations(exported, result).table)
    return result, {'output': exported.name, 'input_rows': len(table), 'output_rows': count,
                    'operations': list(operations)}


def picasso(pipeline, source, config, output):
    from picasso import io, postprocess

    settings = config['postfit']
    path = Path(source['path'])
    if path.suffix.lower() not in ('.h5', '.hdf5') or not path.with_suffix('.yaml').is_file():
        raise ValueError('Picasso post-fitting requires a Picasso HDF5 table with its matching YAML file.')
    locs, info = io.load_locs(str(path))
    count = len(locs)
    pixel = source['pixel_size_nm']
    keep = np.ones(count, dtype=bool)
    minimum = settings.get('min_photons')
    maximum = settings.get('max_precision_nm')
    linking = settings.get('link')
    if linking or maximum is not None:
        if not {'lpx', 'lpy'}.issubset(locs.dtype.names):
            raise ValueError('Picasso precision filtering and Link require the lpx and lpy columns.')
        keep &= np.isfinite(locs.lpx) & np.isfinite(locs.lpy) & (locs.lpx > 0) & (locs.lpy > 0)
    if minimum is not None:
        if 'photons' not in locs.dtype.names:
            raise ValueError('Photon filtering requires the Picasso photons column.')
        keep &= np.isfinite(locs.photons) & (locs.photons >= minimum)
    if maximum is not None:
        keep &= np.maximum(locs.lpx, locs.lpy)*pixel <= maximum
    locs = locs[keep]
    if linking:
        locs = postprocess.link(locs, info, r_max=settings['link_nm']/pixel,
                                max_dark_time=settings['dark_frames'], remove_ambiguous_lengths=False)
    if not len(locs):
        raise ValueError('Picasso post-fitting removed every localization.')
    target = output / 'postfit.hdf5'
    # Preserve already corrected coordinates, including negative positions at the field edge.
    import h5py
    with h5py.File(target, 'w') as handle:
        handle.create_dataset('locs', data=locs)
    io.save_info(str(target.with_suffix('.yaml')), info + [{'Generated by': 'MorSTORM Picasso post-fitting',
                                                          'Pixelsize': pixel, 'Post-fitting': settings}])
    return {'path': str(target), 'format': 'picasso', 'pixel_size_nm': pixel}, {
        'output': target.name, 'input_rows': count, 'output_rows': len(locs), 'operations': settings}


def run(pipeline, stage, source, config, output):
    if stage == 'reconstruct':
        return thunderstorm(pipeline, source, config, output, reconstruction=True)
    if config['parameter_preset'] == 'Picasso':
        return picasso(pipeline, source, config, output)
    p = config['postfit']
    operations = []
    if p['formula']:
        formula = p['formula']
        if any(char in formula for char in '[]\r\n'):
            raise ValueError('A ThunderSTORM filter expression cannot contain brackets or newlines.')
        operations.append(f'action=filter formula=[{formula}]')
    if p['duplicates']:
        operations.append(f'action=duplicates distformula=[{p["duplicate_nm"]:.17g}]')
    if p['density']:
        operations.append(f'action=density radius={p["density_nm"]:.17g} dimensions={p["dimensions"]} neighbors={p["neighbors"]}')
    if p['merge']:
        operations.append(f'action=merge dist={p["merge_nm"]:.17g} offframes={p["dark_frames"]} '
                          f'framespermolecule={p["max_frames"]} zcoordweight={p["z_weight"]:.17g}')
    return thunderstorm(pipeline, source, config, output, operations)


if __name__ == '__main__':
    _, stage, source_path, config_path, output_dir = sys.argv
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    source = json.loads(Path(source_path).read_text(encoding='utf-8'))
    output = Path(output_dir)
    pipeline = import_module('morstorm.pipeline')
    updated, metadata = run(pipeline, stage, source, config, output)
    (output / f'{stage}-result.json').write_text(json.dumps({'input': updated, 'metadata': metadata}), encoding='utf-8')
