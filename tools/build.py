"""Embeds tools/data.json into tools/pokemon_hack_porter_src.py and writes the
single-file program pokemon_hack_porter.py in the repository root."""
import base64, os, zlib
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, 'pokemon_hack_porter_src.py'), encoding='utf-8').read()
blob = base64.b64encode(zlib.compress(open(os.path.join(here, 'data.json'), 'rb').read(), 9)).decode()
lines = '\n'.join(blob[i:i + 100] for i in range(0, len(blob), 100))
out = src.replace('DATA_BLOB = "@@DATA@@"', 'DATA_BLOB = """\n' + lines + '\n"""')
open(os.path.join(here, '..', 'pokemon_hack_porter.py'), 'w', encoding='utf-8').write(out)
print('wrote pokemon_hack_porter.py')
