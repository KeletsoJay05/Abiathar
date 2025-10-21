from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file, jsonify
from flask_login import login_required, current_user
from models import db, Course, Assignment, Enrollment, Submission, LectureMaterial, Notification
from utils import save_uploaded_file, save_lecture_material, get_file_type
from notifications import get_unread_count, mark_as_read, mark_all_as_read
import os

student_bp = Blueprint('student', __name__)

@student_bp.route('/student/dashboard')
@login_required
def dashboard():
    if current_user.role != 'student':
        flash('Student access required', 'error')
        return redirect(url_for('auth.login'))
    
    # Get enrolled courses
    enrollments = Enrollment.query.filter_by(
        user_id=current_user.id, 
        status='active'
    ).all()
    
    enrolled_courses = []
    for enrollment in enrollments:
        course = Course.query.get(enrollment.course_id)
        if course:
            enrolled_courses.append(course)
    
    # Get assignments for enrolled courses
    course_ids = [course.id for course in enrolled_courses]
    assignments = []
    if course_ids:
        assignments = Assignment.query.filter(Assignment.course_id.in_(course_ids)).all()
    
    # Get submissions
    student_submissions = Submission.query.filter_by(student_id=current_user.id).all()
    submissions = {sub.assignment_id: sub for sub in student_submissions}
    
    return render_template('student/dashboard.html',
                         enrolled_courses=enrolled_courses,
                         assignments=assignments,
                         submissions=submissions)

@student_bp.route('/student/assignments')
@login_required
def assignments():
    if current_user.role != 'student':
        flash('Student access required', 'error')
        return redirect(url_for('auth.login'))
    
    # Get enrolled courses
    enrollments = Enrollment.query.filter_by(
        user_id=current_user.id, 
        status='active'
    ).all()
    
    course_ids = [enrollment.course_id for enrollment in enrollments]
    
    # Get assignments
    assignments = []
    if course_ids:
        assignments = Assignment.query.filter(Assignment.course_id.in_(course_ids)).all()
    
    # Get submissions
    student_submissions = Submission.query.filter_by(student_id=current_user.id).all()
    submissions = {sub.assignment_id: sub for sub in student_submissions}
    
    return render_template('student/assignments.html',
                         assignments=assignments,
                         submissions=submissions)

@student_bp.route('/student/grades')
@login_required
def grades():
    if current_user.role != 'student':
        flash('Student access required', 'error')
        return redirect(url_for('auth.login'))
    
    # Get graded submissions
    graded_submissions = Submission.query.filter_by(
        student_id=current_user.id
    ).all()
    
    # Filter for graded submissions
    graded_submissions = [sub for sub in graded_submissions if sub.marks is not None]
    
    return render_template('student/grades.html',
                         submissions=graded_submissions)

@student_bp.route('/student/submit-assignment/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
def submit_assignment(assignment_id):
    if current_user.role != 'student':
        flash('Student access required', 'error')
        return redirect(url_for('auth.login'))
    
    assignment = Assignment.query.get(assignment_id)
    
    if not assignment:
        flash('Assignment not found', 'error')
        return redirect(url_for('student.assignments'))
    
    # Check enrollment
    enrollment = Enrollment.query.filter_by(
        user_id=current_user.id,
        course_id=assignment.course_id,
        status='active'
    ).first()
    
    if not enrollment:
        flash('You are not enrolled in this course', 'error')
        return redirect(url_for('student.assignments'))
    
    # Check existing submission
    existing_submission = Submission.query.filter_by(
        assignment_id=assignment_id,
        student_id=current_user.id
    ).first()
    
    if request.method == 'POST':
        if existing_submission:
            flash('You have already submitted this assignment', 'error')
            return redirect(url_for('student.assignments'))
        
        # Handle file upload
        if 'submission_file' not in request.files:
            flash('No file selected', 'error')
            return render_template('student/submit_assignment.html',
                                 assignment=assignment,
                                 existing_submission=existing_submission)
        
        file = request.files['submission_file']
        
        if file.filename == '':
            flash('No file selected', 'error')
            return render_template('student/submit_assignment.html',
                                 assignment=assignment,
                                 existing_submission=existing_submission)
        
        # Save file
        file_path = save_uploaded_file(file, 'submissions')
        
        if not file_path:
            flash('Invalid file type. Allowed: PDF, DOC, DOCX, TXT, JPG, PNG, GIF, ZIP, PPT', 'error')
            return render_template('student/submit_assignment.html',
                                 assignment=assignment,
                                 existing_submission=existing_submission)
        
        # Create submission
        submission = Submission(
            assignment_id=assignment_id,
            student_id=current_user.id,
            file_path=file_path,
            feedback=request.form.get('notes', ''),
            status='submitted'
        )
        
        db.session.add(submission)
        db.session.commit()
        
        flash('Assignment submitted successfully!', 'success')
        return redirect(url_for('student.assignments'))
    
    return render_template('student/submit_assignment.html',
                         assignment=assignment,
                         existing_submission=existing_submission)

@student_bp.route('/download/submission/<int:submission_id>')
@login_required
def download_submission(submission_id):
    """Download student's own submission"""
    submission = Submission.query.get(submission_id)
    
    if not submission or submission.student_id != current_user.id:
        flash('File not found', 'error')
        return redirect(url_for('student.assignments'))
    
    if not submission.file_path:
        flash('No file attached', 'error')
        return redirect(url_for('student.assignments'))
    
    return send_file(
        f"static/uploads/{submission.file_path}",
        as_attachment=True,
        download_name=f"submission_{submission.assignment.title}.{submission.file_path.split('.')[-1]}"
    )

# LECTURE MATERIALS ROUTES

@student_bp.route('/student/course-materials/<int:course_id>')
@login_required
def course_materials(course_id):
    if current_user.role != 'student':
        flash('Student access required', 'error')
        return redirect(url_for('auth.login'))
    
    # Check enrollment
    enrollment = Enrollment.query.filter_by(
        user_id=current_user.id,
        course_id=course_id,
        status='active'
    ).first()
    
    if not enrollment:
        flash('You are not enrolled in this course', 'error')
        return redirect(url_for('student.dashboard'))
    
    course = Course.query.get(course_id)
    if not course:
        flash('Course not found', 'error')
        return redirect(url_for('student.dashboard'))
    
    # Get published materials for this course
    materials = LectureMaterial.query.filter_by(
        course_id=course_id,
        is_published=True
    ).order_by(LectureMaterial.week_number, LectureMaterial.created_at.desc()).all()
    
    # Group materials by week
    materials_by_week = {}
    for material in materials:
        week = material.week_number if material.week_number else "General"
        if week not in materials_by_week:
            materials_by_week[week] = []
        materials_by_week[week].append(material)
    
    return render_template('student/course_materials.html',
                         course=course,
                         materials_by_week=materials_by_week)

@student_bp.route('/student/download-material/<int:material_id>')
@login_required
def download_material(material_id):
    """Student downloads lecture material"""
    material = LectureMaterial.query.get(material_id)
    
    if not material or not material.is_published:
        flash('Material not found', 'error')
        return redirect(url_for('student.dashboard'))
    
    # Check enrollment
    enrollment = Enrollment.query.filter_by(
        user_id=current_user.id,
        course_id=material.course_id,
        status='active'
    ).first()
    
    if not enrollment:
        flash('Access denied', 'error')
        return redirect(url_for('student.dashboard'))
    
    if material.file_type == 'link':
        # Redirect to external link
        return redirect(material.file_path)
    
    file_path = os.path.join('static/uploads', material.file_path)
    if not os.path.exists(file_path):
        flash('File not found on server', 'error')
        return redirect(url_for('student.course_materials', course_id=material.course_id))
    
    # Create clean filename
    original_extension = material.file_path.split('.')[-1]
    clean_title = "".join(c for c in material.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=f"{clean_title}.{original_extension}"
    )

# NOTIFICATION ROUTES

@student_bp.route('/student/notifications')
@login_required
def notifications():
    if current_user.role != 'student':
        flash('Student access required', 'error')
        return redirect(url_for('auth.login'))
    
    # Get all notifications for current user
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).all()
    
    return render_template('student/notifications.html',
                         notifications=notifications)

@student_bp.route('/student/notifications/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    if current_user.role != 'student':
        return jsonify({'success': False, 'error': 'Access denied'})
    
    notification = mark_as_read(notification_id, current_user.id)
    if notification:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Notification not found'})

@student_bp.route('/student/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    if current_user.role != 'student':
        return jsonify({'success': False, 'error': 'Access denied'})
    
    mark_all_as_read(current_user.id)
    return jsonify({'success': True})

@student_bp.route('/student/notifications/unread-count')
@login_required
def get_unread_notifications_count():
    if current_user.role != 'student':
        return jsonify({'count': 0})
    
    count = get_unread_count(current_user.id)
    return jsonify({'count': count})