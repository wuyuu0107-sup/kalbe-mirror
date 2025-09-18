import psycopg2

DATABASE_URL = "postgresql://postgres:YOUR-PASSWORD@db.jfgndcfxzgxbyxjlamgg.supabase.co:5432/postgres?sslmode=require"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT NOW();")
    print("Connected! Current time:", cur.fetchone())
    cur.close()
    conn.close()
except Exception as e:
    print("Connection failed:", e)