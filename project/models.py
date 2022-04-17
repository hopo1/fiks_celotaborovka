# models.py

from flask_login import UserMixin
from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import relationship

from . import db
from project.enums import Roles


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)  # primary keys are required by SQLAlchemy
    password = db.Column(db.String(100))
    name = db.Column(db.String(100), unique=True)
    role = db.Column(db.Enum(Roles))
    points = db.Column(db.Integer, default=0)


class Tile(db.Model):
    x = db.Column(db.Integer, primary_key=True)
    y = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(ForeignKey('user.id'))
    sub = db.Column(db.TIMESTAMP, default=func.now())
    solved = db.Column(db.Boolean, default=False)
    player = relationship("User", foreign_keys=[player_id])


class Range(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    min_x = db.Column(db.Integer)
    max_x = db.Column(db.Integer)
    min_y = db.Column(db.Integer)
    max_y = db.Column(db.Integer)


class Color(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    x = db.Column(db.Float)
    y = db.Column(db.Float)
    z = db.Column(db.Float)
    user_id = db.Column(ForeignKey('user.id'), unique=True)
