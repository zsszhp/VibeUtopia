Set-Location D:\project\VibeUtopia
git add -A
git status --porcelain | Out-File commit_status.txt
git commit -m "chore: 更新 .gitignore 补充清理规则（重复运行时数据、LFS日志、node_modules日志、临时检查文件），清理 Python __pycache__ 和重复运行时文件"
git log --oneline -3 | Out-File commit_log.txt
git push gitee main
git push github main
"ALL DONE" | Out-File commit_done.txt
