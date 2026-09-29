# -*- coding: utf-8 -*-
import os
import re

root = r'D:\z\project\my\VibeUtopia'
files = [
    'CLAUDE.md',
    os.path.join('.trae', 'rules', 'project_rules.md'),
    os.path.join('.trae', 'rules', 'Ralph.md'),
    os.path.join('.trae', 'rules', 'git-workflow.md'),
    os.path.join('.trae', 'rules', 'compile-test.md'),
    os.path.join('.trae', 'rules', 'code-quality.md'),
]
pat = re.compile(r'docs/[^\s\)\"\'<>`,]+|(?:^|[\s`(])((?:design|audit|guides|reports)/[^\s\)\"\'<>`,]+)')

for rel in files:
    p = os.path.join(root, rel)
    if not os.path.exists(p):
        print('skip', rel)
        continue
    t = open(p, encoding='utf-8', errors='replace').read()
    hits = []
    for m in re.finditer(r'docs/[^\s\)\"\'<>`,]+', t):
        hits.append(m.group(0))
    for m in re.finditer(r'\b(?:design|audit|guides|reports)/[^\s\)\"\'<>`,]+', t):
        hits.append(m.group(0))
    print(rel, '->', hits if hits else '(clean)')

# also check MEMORY
mem = os.path.join(root, '.monkeycode', 'MEMORY.md')
raw = open(mem, 'rb').read()
try:
    t = raw.decode('utf-8')
    enc = 'utf-8'
except Exception:
    t = raw[:24004].decode('utf-8', errors='replace') + raw[24004:].decode('gbk', errors='replace')
    enc = 'mixed->try'
print('MEMORY encoding readable as', enc, 'len', len(t))
hits = []
for m in re.finditer(r'docs/[^\s\)\"\'<>`,]+', t):
    hits.append(m.group(0))
print('MEMORY docs refs:', hits)

# git status docs
import subprocess
r = subprocess.run(['git', 'status', '--short', 'docs', 'CLAUDE.md', '.monkeycode'], cwd=root, capture_output=True)
print('--- git status docs ---')
print(r.stdout.decode('utf-8', errors='replace'))
