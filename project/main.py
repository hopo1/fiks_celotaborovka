# main.py
import io

from flask import Blueprint, render_template, request, current_app, flash, redirect, url_for, Response
from flask_login import login_required, current_user
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import ListedColormap
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from sqlalchemy import tuple_
from sqlalchemy.exc import IntegrityError
import numpy as np

from .color_solver import get_color, get_colors
from .models import User, Range, Tile
from project.enums import Roles
from . import db

main = Blueprint('main', __name__)


@main.route('/')
def index():
    return render_template('index.html')


@main.route('/profile')
@login_required
def profile():
    if current_user.role == Roles.user:
        u = User.query.filter_by(id=current_user.id).first()
        return render_template('user.html', name=u.name, points=u.points, id=str(u.id))
    else:
        users = User.query.all()
        return render_template('admin.html', name=current_user.name, len=len(users), users=users)


@main.route('/make_admin', methods=['POST'])
@login_required
def make_admin():
    if current_user.role != Roles.admin:
        flash("You can not make admin")
        return redirect(url_for('main.profile'))
    _id = request.form.get('id')
    u = User.query.filter_by(id=_id).first()
    if u.role == Roles.admin:
        flash("already admin")
        return redirect(url_for('main.profile'))
    u.role = Roles.admin
    db.session.add(u)
    db.session.commit()
    return profile()


@main.route('/make_user', methods=['POST'])
@login_required
def make_user():
    if current_user.role != Roles.admin:
        flash("You can not make user")
        return redirect(url_for('main.profile'))
    _id = int(request.form.get('id'))
    if _id == current_user.id:
        flash("You can not demote you")
        return redirect(url_for('main.profile'))
    u = User.query.filter_by(id=_id).first()
    if u.role == Roles.user:
        flash("already user")
        return redirect(url_for('main.profile'))
    u.role = Roles.user
    db.session.add(u)
    db.session.commit()
    return profile()


@main.route('/ocupy', methods=['POST'])
@login_required
def ocupy():
    x = request.form.get('x')
    y = request.form.get('y')
    try:
        x = int(x)
        y = int(y)
    except ValueError:
        flash("Fill x and y!")
        return redirect(url_for('main.profile'))

    id_ = current_user.id
    u = User.query.filter_by(id=id_).first()
    if u.points <= 0:
        flash("Not enougth points.")
        return redirect(url_for('main.profile'))
    u.points = User.points - 1
    db.session.add(u)
    rn = get_range()
    if rn is None:
        flash("Range not specified tell orgs!")
        return redirect(url_for('main.profile'))
    if inside(rn, x, y):
        flash("Out of grid.")
        return redirect(url_for('main.profile'))
    t = Tile(x=x, y=y, player=current_user.id)
    db.session.add(t)
    try:
        db.session.commit()
    except IntegrityError:
        flash("tile already ocupied!")
    return redirect(url_for('main.profile'))


@main.route('/give_points', methods=['POST'])
@login_required
def give_points():
    if current_user.role != Roles.admin:
        return current_app.login_manager.unauthorized()
    id_ = request.form.get('id')
    p = request.form.get('points')
    try:
        p = int(p)
    except ValueError:
        return redirect(url_for('main.profile'))
    m = User.query.filter_by(id=id_).first()
    m.points = User.points + p
    db.session.add(m)
    db.session.commit()
    return profile()


@main.route('/print-plot')
@login_required
def plot_png():  # todo add cache and invalidate on give points
    fig = Figure()
    ax = fig.add_subplot(1, 1, 1)
    cmap = ListedColormap(get_colors())
    rn = get_range()
    arr = np.zeros((rn.max_x - rn.min_x, rn.max_y - rn.min_y))
    ts = Tile.query.all()
    for i in ts:
        arr[i.x - rn.min_x][i.y - rn.min_y] = i.player + 1 if i.solved else 1
    ax.imshow(arr, cmap)
    ax.set_xticks(np.arange(0, rn.max_x - rn.min_x, 1))
    ax.set_yticks(np.arange(0, rn.max_y - rn.min_y, 1))

    # Labels for major ticks
    ax.set_xticklabels(np.arange(rn.min_x, rn.max_x, 1))
    ax.set_yticklabels(np.arange(rn.min_y, rn.max_y, 1))

    # Minor ticks
    ax.set_xticks(np.arange(- .5, rn.max_x - rn.min_x, 1), minor=True)
    ax.set_yticks(np.arange(-.5, rn.max_y - rn.min_y, 1), minor=True)

    # Gridlines based on minor ticks
    ax.grid(which='minor', color='r', linestyle='-', linewidth=2)
    output = io.BytesIO()
    FigureCanvasAgg(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')


@main.route('/evaluate')
@login_required
def evaluate():  # todo test and add a timer
    rn = get_range()
    arr = np.zeros((rn.max_x - rn.min_x, rn.max_y - rn.min_y))
    ts = Tile.query.filter_by(solved=True).all()
    for i in ts:
        arr[i.x - rn.min_x][i.y - rn.min_y] = i.player
    tsf = Tile.query.filter_by(solved=False).order_by(Tile.sub.asc()).all()
    for i in tsf:
        for a, b in ((-1, 0), (0, -1), (1, 0), (0, 1)):
            px, py = i.x + a, i.y + b
            arr[i.x - rn.min_x][i.y - rn.min_y] = i.player
            if inside(rn, px, py) and arr[px][py] != 0 and arr[px][py] != arr[i.x][i.y]:
                sur = is_surrounded(arr, px, py, rn)
                if sur:
                    db.session.query(Tile).filter(tuple_(Tile.x, Tile.y).in_(sur)).update({'player': i.player})
                    for c, d in sur:
                        arr[c - rn.min_x][d - rn.min_y] = i.player
        i.solved = True
        db.session.add(i)
        db.session.commit()


def get_range():
    return Range.query.order_by(Range.id.desc()).first()


def inside(rn, x, y):
    return rn.min_x > x or rn.max_x <= x or rn.min_y > y or rn.max_y <= y


def is_surrounded(arr, px, py, rn):
    visited = set()
    to_visit = set()
    to_visit.add((px, py))
    while len(to_visit) != 0:
        x, y = to_visit.pop()
        visited.add((x, y))
        for a, b in ((-1, 0), (0, -1), (1, 0), (0, 1)):
            if arr[x + a - rn.min_x][y + b - rn.min_x] == 0:
                return False
            if arr[x + a - rn.min_x][y + b - rn.min_x] == arr[x - rn.min_x][y - rn.min_x]:
                to_visit.add((x + a, y + b))
    return visited


'''@main.route('/my_color', methods=['GET'])
@login_required
def getMyColor():
    return get_color(current_user.id)'''
