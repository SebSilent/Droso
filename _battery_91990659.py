import json

def read_json_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

import tempfile, os, json as _j
p = os.path.join(tempfile.mkdtemp(), 'x.jsonl')
open(p, 'w').write('{"a": 1}\n{"a": 2}\n')
assert read_json_lines(p) == [{'a': 1}, {'a': 2}]
