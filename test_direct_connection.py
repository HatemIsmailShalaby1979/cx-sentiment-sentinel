from sqlalchemy import create_engine

# Hardcoded credentials to bypass ConfigManager temporarily
user = "readonly_user"
pw = "Thommy@1979"
host = "localhost"
port = "5432"
db = "ops_db"

print(f"🔄 Trying DIRECT connection to {host}:{port} as user '{user}'...")
dsn = f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}"

try:
    engine = create_engine(dsn, connect_args={'connect_timeout': 5})
    with engine.connect() as conn:
        print("✅ SUCCESS! The Database, Docker, and WSL2 bridge are 100% working.")
except Exception as e:
    print(f"❌ DIRECT CONNECTION FAILED:\n{e}")
