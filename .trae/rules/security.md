---
description: 安全与数据保护
globs:
alwaysApply: true
---

- 绝不将密码/API Key/Token 提交到代码仓库（密钥泄露曾导致生产环境被入侵）
- API Key 必须通过 `.env` 环境变量管理，`.env` 文件不提交到 Git
- `.env.example` 作为模板提交，不含真实密钥
- 文件路径必须校验合法性防路径遍历，外部输入的路径必须校验，禁止直接拼接用户输入到文件路径
- 日志禁止输出密码、Token、API Key、完整身份证号、手机号、邮箱
- 外部请求/响应中的敏感字段必须脱敏
- 所有用户输入必须校验和 sanitize，防 XSS/注入
- SQL 注入防护：使用 SQLAlchemy ORM 或参数化查询，禁止字符串拼接
- XSS 防护：前端对渲染内容做 sanitize
- 文件上传必须校验文件类型和大小
- 新增生成文件类型时检查 .gitignore，确保 build/、.vs/、日志已排除
