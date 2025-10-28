import psycopg
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

try:
    os.environ.get("DATABASE_URL")
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT NOW();")
    print("Connected! Current time:", cur.fetchone())
    cur.close()
    conn.close()
except Exception as e:
    print("Connection failed:", e)