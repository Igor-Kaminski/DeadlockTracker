from app import db
from datetime import datetime
from flask_login import UserMixin


# User model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    steam_account = db.relationship('SteamAccount', backref='user', uselist=False)

    def __repr__(self):
        return f"<User {self.username}>"


# Steam Model for steam info
class SteamAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    steam_id = db.Column(db.String(20), unique=True, nullable=False)
    steam_name = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f"<SteamAccount {self.steam_id}>"


# Store hero related data
class Hero(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    image_url = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f"<Hero {self.name}>"


# Favourite Hero model for profile
class FavouriteHero(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    hero_id = db.Column(db.Integer, db.ForeignKey('hero.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('favourite_heroes', lazy='dynamic'))
    hero = db.relationship('Hero', backref=db.backref('favourited_by', lazy='dynamic'))

    def __repr__(self):
        return f"<FavouriteHero user_id={self.user_id} hero_id={self.hero_id}>"
