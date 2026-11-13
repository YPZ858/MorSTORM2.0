"""Crop an XY region from every TIFF frame and restore fitted XY coordinates."""
import csv
from fractions import Fraction
from itertools import chain
import json
import math
from pathlib import Path
import sys


FULL_FRAME = {'left': 0, 'top': 0, 'right': 100, 'bottom': 100}
STACK_AXES = ('TYX', 'ZYX', 'IYX', 'QYX')


def validate(region):
    if region is None:
        return None
    if not isinstance(region, dict) or region.keys() != FULL_FRAME.keys():
        raise ValueError('Supply left, top, right and bottom crop percentages.')
    try:
        bounds = {key: float(region[key]) for key in FULL_FRAME}
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError('Crop edges must be numbers.') from error
    if not (0 <= bounds['left'] < bounds['right'] <= 100
            and 0 <= bounds['top'] < bounds['bottom'] <= 100):
        raise ValueError('Crop edges must be between 0 and 100%, with left < right and top < bottom.')
    return None if bounds == FULL_FRAME else bounds


def movie_series(tiff):
    if len(tiff.series) != 1 or tiff.series[0].axes not in (*STACK_AXES, 'YX'):
        raise ValueError('Select a single-channel TIFF image or stack of 2D frames.')
    return tiff.series[0]


def crop_tiff(source, target, region, cancelled, pixel_size_nm):
    import numpy as np
    import tifffile

    def edge(key, size, round_edge):
        return round_edge(Fraction(str(region[key])) * size / 100)

    partial = target.with_suffix('.partial')
    try:
        with tifffile.TiffFile(source) as tiff:
            series = movie_series(tiff)
            height, width = series.shape[-2:]
            frames = series.shape[0] if series.axes in STACK_AXES else 1
            left, top = edge('left', width, math.floor), edge('top', height, math.floor)
            right, bottom = edge('right', width, math.ceil), edge('bottom', height, math.ceil)
            crop_height, crop_width = bottom - top, right - left
            # The pinned Picasso TIFF reader uses 32-bit offsets.
            if frames * (crop_height * crop_width * series.dtype.itemsize + 512) >= 2**32:
                raise ValueError('The cropped stack is too large for standard TIFF. Choose a smaller region.')
            if len(series.pages) == frames and series.pages[0].shape == (height, width):
                images = (page.asarray() for page in series.pages)
            else:
                try:
                    mapped = tifffile.memmap(source, series=0)
                except ValueError as error:
                    raise ValueError('This TIFF layout cannot be cropped frame by frame.') from error
                images = iter(mapped.reshape(frames, height, width))
            with tifffile.TiffWriter(partial, byteorder='<', bigtiff=False) as output:
                for frame in images:
                    if cancelled():
                        return None
                    output.write(np.ascontiguousarray(frame[top:bottom, left:right]),
                                 photometric='minisblack', metadata=None, contiguous=True,
                                 rowsperstrip=crop_height)
        if cancelled():
            return None
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    return {'source_tiff': str(source.resolve()), 'working_tiff': str(target.resolve()), 'percent': region,
            'bounds_xyxy_px': [left, top, right, bottom], 'original_shape_yx': [height, width],
            'cropped_shape_yx': [crop_height, crop_width], 'frames': frames,
            'coordinate_offset_xy_nm': [left * pixel_size_nm, top * pixel_size_nm]}


def restore_localizations(path, crop):
    left, top, _, _ = crop['bounds_xyxy_px']
    if path.suffix.lower() == '.csv':
        temporary = path.with_suffix('.csv.partial')
        try:
            with path.open(encoding='utf-8-sig', newline='') as source, temporary.open('w', encoding='utf-8', newline='') as target:
                reader = csv.reader(source)
                header = next(reader, [])
                first = next(reader, None)
                if not first:
                    raise ValueError('ThunderSTORM found no localizations in the cropped TIFF. Check the crop region and fitting parameters.')
                if not {'x [nm]', 'y [nm]'}.issubset(header):
                    raise ValueError('ThunderSTORM CSV is missing its X or Y column in nanometers.')
                x, y = (header.index(name) for name in ('x [nm]', 'y [nm]'))
                dx, dy = crop['coordinate_offset_xy_nm']
                writer = csv.writer(target)
                writer.writerow(header)
                for row in chain((first,), reader):
                    row[x] = str(float(row[x]) + dx)
                    row[y] = str(float(row[y]) + dy)
                    writer.writerow(row)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    else:
        import h5py
        import yaml

        with h5py.File(path, 'r+') as output:
            data = output['locs']
            if not len(data):
                raise ValueError('Picasso found no localizations in the cropped TIFF. Check the crop region and fitting parameters.')
            for start in range(0, len(data), 65536):
                rows = data[start:start+65536]
                rows['x'] += left
                rows['y'] += top
                data[start:start+len(rows)] = rows
        sidecar = path.with_suffix('.yaml')
        with sidecar.open(encoding='utf-8') as source:
            info = list(yaml.safe_load_all(source))
        height, width = crop['original_shape_yx']
        info[0].update(Height=height, Width=width, File=crop['source_tiff'])
        info[0]['MorSTORM crop'] = crop
        with sidecar.open('w', encoding='utf-8') as target:
            yaml.safe_dump_all(info, target)


if __name__ == '__main__':
    config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
    restore_localizations(Path(sys.argv[2]), config['crop_applied'])
