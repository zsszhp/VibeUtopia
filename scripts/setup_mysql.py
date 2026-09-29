import os
import sys

import pymysql

# 口令从环境变量读取，禁止硬编码
root_password = os.getenv("MYSQL_ROOT_PASSWORD", "")
app_password = os.getenv("MYSQL_PASSWORD", "")
app_user = os.getenv("MYSQL_USER", "vibe_user")
database = os.getenv("MYSQL_DATABASE", "vibeutopia")
host = os.getenv("MYSQL_HOST", "localhost")
port = int(os.getenv("MYSQL_PORT", "3306"))

if not root_password:
    sys.exit("MYSQL_ROOT_PASSWORD 未设置，请在 .env 中配置后重试")
if not app_password:
    sys.exit("MYSQL_PASSWORD 未设置，请在 .env 中配置后重试")

conn = pymysql.connect(host=host, port=port, user="root", password=root_password)
cur = conn.cursor()
cur.execute(
    f"CREATE DATABASE IF NOT EXISTS {database} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
)
try:
    cur.execute(
        f"CREATE USER IF NOT EXISTS '{app_user}'@'localhost' IDENTIFIED BY %s",
        (app_password,),
    )
except Exception:
    pass
cur.execute(f"GRANT ALL PRIVILEGES ON {database}.* TO '{app_user}'@'localhost'")
cur.execute("FLUSH PRIVILEGES")
cur.execute("SHOW DATABASES")
print("Databases:", [r[0] for r in cur.fetchall()])
conn.close()
print("MySQL setup complete!")
