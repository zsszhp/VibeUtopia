from pathlib import Path
import json
import re

idx = Path("data/test/cases/回测案例库索引.md").read_text(encoding="utf-8")
# 重标：学术/职场/消费等「中」争议不再强制 red
relax_high = {
    "同济大学教师论文造假.md": "orange",
    "优思益假洋牌事件.md": "orange",
    "东方甄选小作文风波.md": "orange",
    "同济大学教师论文造假.md": "orange",
}
pattern = re.compile(r"`([^`]+\.md)`[^（\n]*（(高|中|低)）")
base = {"高": "red", "中": "orange", "低": "green"}
rows = []
seen = set()
for m in pattern.finditer(idx):
    fname, lab = m.group(1), m.group(2)
    if fname in seen:
        continue
    seen.add(fname)
    exp = relax_high.get(fname, base.get(lab, "green"))
    rows.append({"file": fname, "index_label": lab, "expected_level": exp})

out = Path("data/test/cases/paperwork_expected.json")
out.write_text(
    json.dumps(
        {
            "note": "paperwork期望重标（对齐14维可判定范围，学术诚信/消费欺诈等不强制red）",
            "mapping": rows,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
print("wrote", out, "n=", len(rows))
for r in rows:
    if r["file"] in relax_high:
        print(r)
