"""Call the released Python stage functions with one input and one result folder."""
from importlib import import_module
import json
from pathlib import Path
import sys

import raw_crop
import table_stages

def run(package, config_path):
    import numpy as np
    import pandas as pd
    import tifffile

    pipeline = import_module(f'{package}.pipeline')
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    output = Path(config['output_dir'])
    inp = config['input']
    locs = None
    result = {}

    for module in config['modules']:
        print(f'::morstorm-stage::{module}', flush=True)
        if module == 'localize':
            if 'crop_applied' in config:
                config['input']['path'] = config['crop_applied']['working_tiff']
            inp = pipeline._localize(config, output)
            if 'crop_applied' in config:
                raw_crop.restore_localizations(Path(inp['path']), config['crop_applied'])
            result['localization'] = {'backend': config['localization']['backend'], 'output': Path(inp['path']).name}
        if module in ('postfit', 'reconstruct'):
            inp, result[module] = table_stages.run(pipeline, module, inp, config, output)
            if module == 'postfit':
                locs = None
        if locs is None:
            locs = pipeline.read_localizations(inp['path'], inp)
        if module == 'drift':
            drift = {**config['drift'], '_run_dir': str(output/'drift-author')}
            curve, result['drift'] = pipeline.estimate(locs.table, drift)
            locs.table[locs.axes] = locs.table[locs.axes].to_numpy() - curve[locs.table.frame.to_numpy() - 1]
            pipeline.write_exports(locs, output)
            picasso = locs.metadata['format'] == 'picasso'
            inp = {'path': str(output / ('picasso_corrected.hdf5' if picasso else 'corrected.csv')),
                   'format': 'picasso' if picasso else 'csv', 'pixel_size_nm': drift['pixel_size_nm']}
            pd.DataFrame(np.column_stack((np.arange(1, len(curve) + 1), curve)),
                         columns=['frame'] + ['d' + axis for axis in locs.axes]).to_csv(
                output/'drift.csv', index=False, float_format='%.12g')
        elif module == 'morphology':
            image, rendering = pipeline.render(locs.table, config['render'])
            tifffile.imwrite(output/'density.tif', image, photometric='minisblack', metadata=None)
            locs.table[['x_nm','y_nm']].to_csv(output/'coordinates.csv', index=False, float_format='%.17g')
            (output/'render.json').write_text(json.dumps(rendering,indent=2),encoding='utf-8')
            result['render'] = rendering
            result['morphology'] = pipeline.morphology(output, rendering, config['morphology'])

    result.update(localizations=len(locs.table), last_frame=int(locs.table.frame.max()))
    (output/'stage-result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


if __name__ == '__main__':
    run(sys.argv[1],sys.argv[2])
