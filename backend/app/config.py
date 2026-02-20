import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

GOOGLE_CLOUD_PROJECT: str = os.environ["GOOGLE_CLOUD_PROJECT"]
VERTEX_AI_LOCATION: str = os.getenv("VERTEX_AI_LOCATION", "global")
GEMINI_MODEL: str = "gemini-3-flash-preview"
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

FERNET_KEY: bytes = os.environ["FERNET_KEY"].encode()
fernet = Fernet(FERNET_KEY)

STATE_SECRET_KEY: str = os.environ["STATE_SECRET_KEY"]

GOOGLE_OAUTH_CLIENT_ID: str = os.environ["GOOGLE_OAUTH_CLIENT_ID"]
GOOGLE_OAUTH_CLIENT_SECRET: str = os.environ["GOOGLE_OAUTH_CLIENT_SECRET"]
OAUTH_REDIRECT_URI: str = os.environ["OAUTH_REDIRECT_URI"]

FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

GMAIL_SCOPES: list[str] = ["https://www.googleapis.com/auth/gmail.readonly"]

CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
