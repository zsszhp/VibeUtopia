import pymysql

conn = pymysql.connect(host='localhost', port=3306, user='root', password='123456')
cur = conn.cursor()
cur.execute('CREATE DATABASE IF NOT EXISTS vibeutopia CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
try:
    cur.execute("CREATE USER IF NOT EXISTS 'vibe_user'@'localhost' IDENTIFIED BY 'vibe_password'")
except Exception:
    pass
cur.execute("GRANT ALL PRIVILEGES ON vibeutopia.* TO 'vibe_user'@'localhost'")
cur.execute('FLUSH PRIVILEGES')
cur.execute('SHOW DATABASES')
print('Databases:', [r[0] for r in cur.fetchall()])
conn.close()
print('MySQL setup complete!')
