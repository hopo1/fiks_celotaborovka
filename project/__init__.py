# init.py
from werkzeug.utils import import_string
import werkzeug
werkzeug.import_string = import_string

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_caching import Cache
from flask_bootstrap import Bootstrap

# init SQLAlchemy so we can use it later in our models
db = SQLAlchemy()
cache = Cache()


def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = '9OLWxND4o83j4K4iuopO'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
    app.config["CACHE_TYPE"] = "SimpleCache"  # better not use this type w. gunicorn

    cache.init_app(app)
    db.init_app(app)
    Bootstrap(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    cache.clear()

    from .models import User
    '''with app.app_context():
        db.drop_all()
        db.create_all()'''

    @login_manager.user_loader
    def load_user(user_id):
        # since the user_id is just the primary key of our user table, use it in the query for the user
        return User.query.get(int(user_id))

    # blueprint for auth routes in our app
    from project.auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)

    # blueprint for non-auth parts of app
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)



    return app

if __name__ == '__main__':
    app = create_app()
    app.run()
