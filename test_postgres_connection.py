import sys
from shared_utils.config_manager import ConfigManager
from sqlalchemy import create_engine

config = ConfigManager()
host = config.get("DB_HOST", "localhost")
port = config.get("DB_PORT", "5432")
user = config.get("DB_USER", "readonly_user")
pw = config.get("DB_PASS", "")
db = config.get("DB_NAME", "ops_db")

print(f"🔄 Trying to connect to {host}:{port} as user '{user}'...")
dsn = f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}"

try:
    engine = create_engine(dsn, connect_args={'connect_timeout': 5})
    with engine.connect() as conn:
        print("✅ SUCCESS! The WSL2-to-Docker bridge is working perfectly.")
except Exception as e:
    print(f"❌ CONNECTION FAILED:\n{e}")
