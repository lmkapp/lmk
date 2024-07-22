import os

VERSION = "1.2.0.dev2"

API_URL = "https://api.lmkapp.dev"

APP_ID = "10000000-0000-0000-0000-000000000000"

PACKAGE_DIR = os.path.dirname(__file__)

# Sigh, just to make the vercel build work; sqlite3
# docs not exist there, so the cli() setup fails. Side
# note though--is that the wrong place to be doing that setup
# if it runs _even on a --help command???_
DOCS_ONLY = bool(os.getenv("LMK_CLI_DOCS_ONLY"))
