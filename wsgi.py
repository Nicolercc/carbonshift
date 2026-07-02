"""WSGI entrypoint for production servers (gunicorn, uWSGI, etc.)."""

from dotenv import load_dotenv
load_dotenv()

from src.db.init_db import init_db
from src.web.app import app

init_db()
