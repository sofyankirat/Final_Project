"""WSGI entrypoint that loads the Flask app from `front-end/app.py`.

This loader avoids issues with the `front-end` directory name (contains a
hyphen) by loading the module from file path so Gunicorn can import `wsgi:app`.
"""
import importlib.util
from pathlib import Path

APP_PATH = Path(__file__).parent / 'front-end' / 'app.py'

spec = importlib.util.spec_from_file_location('frontend_app', str(APP_PATH))
frontend_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frontend_app)

# Expose the Flask application object for Gunicorn
app = getattr(frontend_app, 'app')
