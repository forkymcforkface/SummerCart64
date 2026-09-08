"""Use the same stock-pin control/status/data-path gate for the raw decoder."""
from pathlib import Path
import json
import sys

base=Path(__file__).resolve().parent.parent/'stock-fit/liveness.py'
exec(compile(base.read_text(),str(base),'exec'))
if __name__=='__main__':
    nets=json.loads(Path(sys.argv[1]).read_text())['modules']['top']['netnames']
    pixel=nets['gif_engine.decoder.out_byte']['bits']
    if len(pixel)!=8 or not all(isinstance(b,int) for b in pixel) or pixel!=nets['gif_engine.out_byte']['bits']:
        raise ValueError('missing data path: direct decoded index stream')
