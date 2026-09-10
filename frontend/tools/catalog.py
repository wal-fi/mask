"""Ancora privada do catalogo exato e modelos atuais, sem dependencia HTTP no loader."""

import hashlib
import json
from pathlib import Path
from maskgw.admin.ui.protocol import validate_presentation

root = Path(__file__).resolve().parents[2]
p = validate_presentation((root / "frontend/private/presentation.json").read_bytes())
calls = [(c.method, c.path, c.input, c.output, c.operation, c.identity, c.error) for c in p.calls]
models = json.dumps([m.model_dump() for m in p.models], sort_keys=True, separators=(",", ":"))
text = '"""Generated closed private catalog; checked against HTTP sources by tests."""\n\n'
text += "CALLS: tuple[tuple[str, str, str | None, str, str, str | None, str], ...] = (\n"
for row in calls:
    text += "    " + repr(row) + ",\n"
text += ')\nMODEL_SHA256 = "' + hashlib.sha256(models.encode()).hexdigest() + '"\n'
(root / "src/maskgw/admin/ui/_catalog.py").write_text(text, encoding="utf-8", newline="\n")
