import json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=json.loads((R/'screens.json').read_text())
assert len({x['id'] for x in s})==len(s)
for x in s:
 assert (R/'screens'/f"{x['id']}.svg").exists()
 assert (R/'screens'/f"{x['id']}.png").exists()
print('V1.4 current manifest validated:',len(s))
