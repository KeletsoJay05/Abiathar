from flask import Flask, redirect
from flask_login import LoginManager
import os
from config import Config
from models import db, User, Course

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    
    # Initialize Login Manager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Create directories
    os.makedirs('static/uploads/profiles', exist_ok=True)
    os.makedirs('static/uploads/assignments', exist_ok=True)
    os.makedirs('static/uploads/submissions', exist_ok=True)
    os.makedirs('static/uploads/materials', exist_ok=True)
    
    return app

app = create_app()

# Import and register blueprints AFTER app creation
from auth import auth_bp
from admin import admin_bp
from teacher import teacher_bp
from student import student_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(teacher_bp)
app.register_blueprint(student_bp)

@app.route('/')
def home():
    return redirect('/login')

def setup_database():
    with app.app_context():
        db.create_all()
        
        # Create default courses
        if Course.query.count() == 0:
            courses = [
                Course(name='Accounting', description='Financial Accounting'),
                Course(name='Math', description='Mathematics'),
                Course(name='Physics', description='Physics')
            ]
            db.session.add_all(courses)
            db.session.commit()
            print("✅ Courses created")
        
        # Create default admin
        if User.query.filter_by(role='admin').count() == 0:
            admin = User(
                username='admin',
                name='System Admin',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin created - username: admin, password: admin123")

if __name__ == '__main__':
    setup_database()
    port = int(os.environ.get("PORT", 5000))
    setup_database()
    print(f"🎓 Abiathar EduConnect Running on port {port}")

    app.run(host='0.0.0.0', port=port, debug=False)  # ← debug=False for production
