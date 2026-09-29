# -*- coding: utf-8 -*-
import os
import re

ROOT = r'D:\z\project\my\VibeUtopia'

fixes = [
    ('docs/docs/', 'docs/'),
    ('docs/02_系统设计/docs/', 'docs/'),
    ('docs/01_产品与需求/docs/', 'docs/'),
    ('docs/03_使用与运维/docs/', 'docs/'),
    ('docs/04_规范与工程/docs/', 'docs/'),
    ('docs/05_调研审计/docs/', 'docs/'),
    ('docs/06_实施记录/docs/', 'docs/'),
    ('docs/07_研究与参考/docs/', 'docs/'),
    ('docs/08_阶段报告/docs/', 'docs/'),
    ('docs/02_系统设计/01_产品与需求/', 'docs/01_产品与需求/'),
    ('docs/02_系统设计/03_使用与运维/', 'docs/03_使用与运维/'),
    ('docs/02_系统设计/04_规范与工程/', 'docs/04_规范与工程/'),
    ('docs/02_系统设计/05_调研审计/', 'docs/05_调研审计/'),
    ('docs/02_系统设计/06_实施记录/', 'docs/06_实施记录/'),
    ('docs/02_系统设计/07_研究与参考/', 'docs/07_研究与参考/'),
    ('docs/02_系统设计/08_阶段报告/', 'docs/08_阶段报告/'),
]

targets = [os.path.join(ROOT, '.monkeycode', 'MEMORY.md'), os.path.join(ROOT, 'CLAUDE.md')]

# also scan all docs
for dirpath, dirs, files in os.walk(os.path.join(ROOT, 'docs')):
    for f in files:
        if f.endswith('.md'):
            targets.append(os.path.join(dirpath, f))

for p in targets:
    if not os.path.exists(p):
        continue
    try:
        text = open(p, encoding='utf-8').read()
    except Exception as e:
        print('skip', p, e)
        continue
    orig = text
    for o, n in fixes:
        while o in text:
            text = text.replace(o, n)
    if text != orig:
        open(p, 'w', encoding='utf-8', newline='').write(text)
        print('fixed', os.path.relpath(p, ROOT))

# recheck MEMORY refs
mem = os.path.join(ROOT, '.monkeycode', 'MEMORY.md')
t = open(mem, encoding='utf-8').read()
print('MEMORY docs refs:')
for m in re.finditer(r'docs/[^\s\)\"\'<>`,]+', t):
    print(' ', m.group(0))
