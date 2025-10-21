import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'abiathar-secret-key-2024'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///abiathar.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    COURSES = ['Accounting', 'Math', 'Physics']
    
    # Allowed file extensions for assignments
    ALLOWED_EXTENSIONS = {
        'pdf', 'doc', 'docx', 'txt', 
        'jpg', 'jpeg', 'png', 'gif',
        'zip', 'rar', 'ppt', 'pptx'
    }
    
    # Allowed file extensions for lecture materials
    ALLOWED_MATERIAL_EXTENSIONS = {
        'pdf', 'doc', 'docx', 'txt', 'ppt', 'pptx',
        'jpg', 'jpeg', 'png', 'gif', 'mp4', 'mov', 'avi',
        'zip', 'rar', 'mp3', 'wav'
    }