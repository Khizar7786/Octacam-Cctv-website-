from .base import *  # noqa: F403


DEBUG = False
SECRET_KEY = "test-only-secret-key-never-use-for-deployment"
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
AUTH_REFRESH_COOKIE_SECURE = True
