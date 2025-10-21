import os
import uuid
from werkzeug.utils import secure_filename
from config import Config

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def allowed_material_file(filename):
    """Check if file type is allowed for lecture materials"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_MATERIAL_EXTENSIONS

def save_uploaded_file(file, folder):
    """Save uploaded file with unique filename"""
    if file and allowed_file(file.filename):
        # Generate unique filename
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        
        # Create file path
        file_path = os.path.join(folder, unique_filename)
        full_path = os.path.join(Config.UPLOAD_FOLDER, file_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Save file
        file.save(full_path)
        return file_path
    
    return None

def save_lecture_material(file, folder='materials'):
    """Save uploaded lecture material with unique filename"""
    if file and allowed_material_file(file.filename):
        # Generate unique filename
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        
        # Create file path
        file_path = os.path.join(folder, unique_filename)
        full_path = os.path.join(Config.UPLOAD_FOLDER, file_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Save file
        file.save(full_path)
        return file_path
    
    return None

def get_file_type(filename):
    """Determine file type for icon display"""
    extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    file_types = {
        'pdf': 'pdf',
        'doc': 'word', 'docx': 'word',
        'ppt': 'powerpoint', 'pptx': 'powerpoint',
        'jpg': 'image', 'jpeg': 'image', 'png': 'image', 'gif': 'image',
        'mp4': 'video', 'mov': 'video', 'avi': 'video',
        'mp3': 'audio', 'wav': 'audio',
        'zip': 'archive', 'rar': 'archive',
        'txt': 'text'
    }
    
    return file_types.get(extension, 'file')