# main.py
import io

from flask import Blueprint, render_template, request, current_app, flash, redirect, url_for, Response
from flask_login import login_required, current_user
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.figure import Figure
from sqlalchemy import tuple_, func
from sqlalchemy.exc import IntegrityError
import numpy as np

from .color_solver import get_colors
from .models import User, Range, Tile
from project.enums import Roles
from . import db, cache

main = Blueprint('main', __name__)


@main.route('/')
def index():
    return render_template('login.html')


@main.route('/admin')
@login_required
def admin():
    users = User.query.all()
    return render_template('admin.html', name=current_user.name, len=len(users), users=users, rn=get_range())


@main.route('/profile')
@login_required
def profile():
    u = User.query.filter_by(id=current_user.id).first()
    return render_template('user.html', name=u.name, points=u.points, id=str(u.id))


@main.route('/make_admin', methods=['POST'])
@login_required
def make_admin():
    if current_user.role != Roles.admin:
        flash("You can not make admin")
        return redirect(url_for('main.admin'))
    _id = request.form.get('id')
    u = User.query.filter_by(id=_id).first()
    if u.role == Roles.admin:
        flash("already admin")
        return redirect(url_for('main.admin'))
    u.role = Roles.admin
    db.session.add(u)
    db.session.commit()
    return admin()


@main.route('/make_user', methods=['POST'])
@login_required
def make_user():
    if current_user.role != Roles.admin:
        flash("You can not make user")
        return redirect(url_for('main.admin'))
    _id = int(request.form.get('id'))
    if _id == current_user.id:
        flash("You can not demote you")
        return redirect(url_for('main.admin'))
    u = User.query.filter_by(id=_id).first()
    if u.role == Roles.user:
        flash("already user")
        return redirect(url_for('main.admin'))
    u.role = Roles.user
    db.session.add(u)
    db.session.commit()
    return admin()


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
    if not_inside(rn, x, y):
        flash("Out of grid.")
        return redirect(url_for('main.profile'))
    t = Tile(x=x, y=y, player_id=current_user.id)
    db.session.add(t)
    try:
        db.session.commit()
    except IntegrityError:
        flash("tile already ocupied!")
    cache.delete_memoized(plot_png)
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
        return redirect(url_for('main.admin'))
    m = User.query.filter_by(id=id_).first()
    m.points = User.points + p
    db.session.add(m)
    db.session.commit()
    return admin()


@main.route('/print-plot')
@login_required
@cache.memoize(0)
def plot_png():  # todo split cache for array and painting if neccesery
    fig = Figure()
    ax = fig.add_subplot(1, 1, 1)
    cl = get_colors()
    cmap = ListedColormap(cl)
    rn = get_range()
    arr = np.zeros((rn.max_x - rn.min_x, rn.max_y - rn.min_y), dtype=np.int)
    ts = Tile.query.all()
    for i in ts:
        arr[i.x - rn.min_x][i.y - rn.min_y] = i.player_id + 1 if i.solved else 1
    norm = BoundaryNorm(np.arange(len(cl) + 1) - .5, len(cl))
    ax.imshow(arr, cmap=cmap, norm=norm)
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


@main.route('/range', methods=['POST'])
@login_required
def increase_range():
    try:
        max_x = int(request.form.get('max_x'))
        min_x = int(request.form.get('min_x'))
        max_y = int(request.form.get('max_y'))
        min_y = int(request.form.get('min_y'))
    except ValueError:
        flash("fill all fields")
        return redirect(url_for('main.admin'))
    rn = get_range()
    if rn is not None and (rn.min_x < min_x or rn.max_x > max_x or rn.min_y < min_y or rn.max_y > max_y):
        flash("field size decrease not allowed")
        return redirect(url_for('main.admin'))
    r = Range(min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y)
    db.session.add(r)
    db.session.commit()
    cache.delete_memoized(get_range)
    cache.delete_memoized(plot_png)
    return admin()


@main.route('/evaluate', methods=["POST"])
@login_required
def evaluate():  # todo test and add a timer
    rn = get_range()
    arr = np.zeros((rn.max_x - rn.min_x, rn.max_y - rn.min_y))
    ts = Tile.query.filter_by(solved=True).all()
    for i in ts:
        arr[i.x - rn.min_x][i.y - rn.min_y] = i.player_id
    tsf = Tile.query.filter_by(solved=False).order_by(Tile.sub.asc()).all()
    for i in tsf:
        for a, b in ((-1, 0), (0, -1), (1, 0), (0, 1)):
            px, py = i.x + a, i.y + b
            pxr, pyr = px - rn.min_x, py - rn.min_y
            arr[i.x - rn.min_x][i.y - rn.min_y] = i.player_id
            if not not_inside(rn, px, py) and arr[pxr][pyr] != 0 and arr[pxr][pyr] != arr[i.x - rn.min_x][
                i.y - rn.min_y]:
                sur = is_surrounded(arr, px, py, rn)
                if sur:
                    db.session.query(Tile).filter(tuple_(Tile.x, Tile.y).in_(sur)).update({'player': i.player_id})
                    for c, d in sur:
                        arr[c - rn.min_x][d - rn.min_y] = i.player_id
        i.solved = True
        db.session.add(i)
        db.session.commit()
    cache.delete_memoized(get_occupied)
    cache.delete_memoized(plot_png)
    return redirect(url_for('main.admin'))


@main.route("/standings")
def results():
    pts = get_occupied()
    return render_template('standings.html', len=len(pts), players=pts)


@cache.memoize(timeout=0)
def get_range():
    return Range.query.order_by(Range.id.desc()).first()


@cache.memoize(timeout=0)
def get_occupied():
    pts = Tile.query.with_entities(Tile.player_id, func.count(Tile.player_id).label('pts')).all()
    nm = {x.player_id: x.pts for x in pts}
    us = User.query.filter_by(role=Roles.user).all()
    return sorted([(x.name, nm.get(x.id, 0)) for x in us], key=lambda x: x[1])


def not_inside(rn, x, y):
    return rn.min_x > x or rn.max_x <= x or rn.min_y > y or rn.max_y <= y


def is_surrounded(arr, px, py, rn):
    visited = set()
    to_visit = set()
    to_visit.add((px, py))
    while len(to_visit) != 0:
        x, y = to_visit.pop()
        visited.add((x, y))
        for a, b in ((-1, 0), (0, -1), (1, 0), (0, 1)):
            if not_inside(rn, x + a, y + b) or arr[x + a - rn.min_x][y + b - rn.min_y] == 0:
                return False
            if arr[x + a - rn.min_x][y + b - rn.min_y] == arr[x - rn.min_x][y - rn.min_y] \
                    and (x + a, y + b) not in visited:
                to_visit.add((x + a, y + b))
    return visited


'''@main.route('/my_color', methods=['GET'])
@login_required
def getMyColor():
    return get_color(current_user.id)'''
