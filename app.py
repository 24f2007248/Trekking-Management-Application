from flask import Flask
from controllers import controllers
from models import admin

def create_app():
    app = Flask(__name__)
    app.secret_key = '123'
    admin.initialize_database()
    controllers.init_app_routes(app)
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)