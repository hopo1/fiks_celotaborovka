from typing import BinaryIO

from flask import send_file

from .models import Color
from . import db, cache
import distinctipy
from PIL import Image

white = (0, 0, 0)
black = (1, 1, 1)


def make_new_color(id):
    r = Color.query.filter_by(user_id=None).first()
    if r is None:
        cls = Color.query.all()
        cls = [(x.x, x.y, x.z) for x in cls]
        cls.append(white)
        cls.append(black)
        new_cls = distinctipy.get_colors(10, cls)
        new_cls = [Color(x=x, y=y, z=z) for x, y, z in new_cls]
        db.session.bulk_save_objects(new_cls)
        db.session.commit()
        r = Color.query.filter_by(user_id=None).first()
    r.user_id = id
    db.session.add(r)
    db.session.commit()
    img = Image.new('RGB', (10, 10), toRgb(r))
    with open('project/static/img/' + str(id) + '_user_img.jpg', 'w+b') as x:
        img.save(x, 'JPEG', quality=70)


def get_colors():
    r = Color.query.filter(Color.user_id.isnot(None)).order_by(Color.user_id.asc()).all()
    return [black,white] + [toRgb(x) for x in r]


def get_color(id):
    r = Color.query.filter_by(user_id=id).first()
    if r is None:
        return None
    img = Image.new('RGB', (10, 10), toRgb(r))
    img_io = BinaryIO()
    img.save(img_io, 'JPEG', quality=70)
    img_io.seek(0)
    return send_file(img_io, mimetype='image/jpeg')


def toRgb(color):
    return int(color.x * 255), int(color.y * 255), int(color.z * 255)
