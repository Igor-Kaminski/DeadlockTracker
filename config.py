import os

# CSRF Protection for secure forms
WTF_CSRF_ENABLED = True
SECRET_KEY = "a-very-secret-key"

# Database setup
basedir = os.path.abspath(os.path.dirname(__file__))
SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(basedir, "app.db")
SQLALCHEMY_TRACK_MODIFICATIONS = False
