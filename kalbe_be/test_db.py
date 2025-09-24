import os
import psycopg2
from dotenv import load_dotenv

# load variables from .env
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT NOW();")
    print("Connected! Current time:", cur.fetchone())
    cur.close()
    conn.close()
except Exception as e:
    print("Connection failed:", e)
