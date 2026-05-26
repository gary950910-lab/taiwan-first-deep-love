import os
from flask import Flask, redirect, url_for

def create_app():
    # Initialize Flask app
    app = Flask(__name__, instance_relative_config=True)
    
    # Simple default configurations
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev_taiwan_first_deep_love_secret_key_12345'),
        DATABASE=os.path.join(app.instance_path, 'database.db'),
    )

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Register blueprints
    from app.routes.backtest import bp as backtest_bp
    app.register_blueprint(backtest_bp)

    # Root route redirecting to /backtest
    @app.route('/')
    def index():
        return redirect(url_for('backtest.index'))

    return app
