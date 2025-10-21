from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from models import db, User, Course, Enrollment, Assignment, Submission, LectureMaterial
from datetime import datetime
import csv
from io import StringIO

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/dashboard')
@login_required
def dashboard():
    if not current_user.is_authenticated or current_user.role != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        # Get comprehensive statistics
        total_students = User.query.filter_by(role='student').count()
        total_teachers = User.query.filter_by(role='teacher').count()
        total_courses = Course.query.count()
        total_assignments = Assignment.query.count()
        total_submissions = Submission.query.count()
        
        # Recent users
        recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
        
        # Recent enrollments with proper data
        recent_enrollments_data = []
        enrollments = Enrollment.query.order_by(Enrollment.enrolled_at.desc()).limit(5).all()
        
        for enrollment in enrollments:
            student = User.query.get(enrollment.user_id)
            course = Course.query.get(enrollment.course_id)
            recent_enrollments_data.append({
                'enrollment': enrollment,
                'student': student,
                'course': course
            })
        
        # Course statistics
        courses_with_stats = []
        for course in Course.query.all():
            student_count = Enrollment.query.filter_by(course_id=course.id, status='active').count()
            assignment_count = Assignment.query.filter_by(course_id=course.id).count()
            courses_with_stats.append({
                'course': course,
                'student_count': student_count,
                'assignment_count': assignment_count
            })
        
        return render_template('admin/dashboard.html',
                            total_students=total_students,
                            total_teachers=total_teachers,
                            total_courses=total_courses,
                            total_assignments=total_assignments,
                            total_submissions=total_submissions,
                            recent_users=recent_users,
                            recent_enrollments=recent_enrollments_data,
                            courses_with_stats=courses_with_stats)
    
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))

# USER MANAGEMENT
@admin_bp.route('/admin/users')
@login_required
def user_management():
    if current_user.role != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('auth.login'))
    
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/admin/users/create', methods=['POST'])
@login_required
def create_user():
    if current_user.role != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('admin.dashboard'))
    
    username = request.form.get('username')
    student_number = request.form.get('student_number')
    name = request.form.get('name')
    role = request.form.get('role')
    password = request.form.get('password')
    
    if not name or not role:
        flash('Name and role are required', 'error')
        return redirect(url_for('admin.user_management'))
    
    # Check for duplicates
    if username and User.query.filter_by(username=username).first():
        flash('Username already exists', 'error')
        return redirect(url_for('admin.user_management'))
    
    if student_number and User.query.filter_by(student_number=student_number).first():
        flash('Student number already exists', 'error')
        return redirect(url_for('admin.user_management'))
    
    user = User(
        username=username if username else None,
        student_number=student_number if student_number else None,
        name=name,
        role=role
    )
    user.set_password(password if password else 'password123')
    
    db.session.add(user)
    db.session.commit()
    
    flash(f'User {name} created successfully!', 'success')
    return redirect(url_for('admin.user_management'))

# REMOVED THE DUPLICATE EDIT_USER ROUTE - KEEP ONLY ONE VERSION
@admin_bp.route('/admin/users/<int:user_id>/edit', methods=['POST'])
@login_required
def edit_user(user_id):
    if current_user.role != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('admin.dashboard'))
    
    user = User.query.get(user_id)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('admin.user_management'))
    
    user.name = request.form.get('name')
    user.role = request.form.get('role')
    
    # Only update if provided
    new_username = request.form.get('username')
    if new_username:
        existing_user = User.query.filter_by(username=new_username).first()
        if existing_user and existing_user.id != user.id:
            flash('Username already exists', 'error')
            return redirect(url_for('admin.user_management'))
        user.username = new_username
    
    new_student_number = request.form.get('student_number')
    if new_student_number:
        existing_user = User.query.filter_by(student_number=new_student_number).first()
        if existing_user and existing_user.id != user.id:
            flash('Student number already exists', 'error')
            return redirect(url_for('admin.user_management'))
        user.student_number = new_student_number
    
    new_password = request.form.get('password')
    if new_password:
        user.set_password(new_password)
    
    db.session.commit()
    flash(f'User {user.name} updated successfully!', 'success')
    return redirect(url_for('admin.user_management'))

@admin_bp.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('admin.dashboard'))
    
    user = User.query.get(user_id)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('admin.user_management'))
    
    if user.id == current_user.id:
        flash('Cannot delete your own account', 'error')
        return redirect(url_for('admin.user_management'))
    
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.name} deleted successfully!', 'success')
    return redirect(url_for('admin.user_management'))

# COURSE MANAGEMENT
@admin_bp.route('/admin/courses')
@login_required
def course_management():
    if current_user.role != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('auth.login'))
    
    courses = Course.query.all()
    # Get enrollment counts for each course
    courses_with_stats = []
    for course in courses:
        student_count = Enrollment.query.filter_by(course_id=course.id, status='active').count()
        teacher_assignments = Assignment.query.filter_by(course_id=course.id).first()
        has_teacher = teacher_assignments is not None
        courses_with_stats.append({
            'course': course,
            'student_count': student_count,
            'has_teacher': has_teacher
        })
    
    return render_template('admin/courses.html', courses_with_stats=courses_with_stats)

@admin_bp.route('/admin/courses/create', methods=['POST'])
@login_required
def create_course():
    if current_user.role != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('admin.dashboard'))
    
    name = request.form.get('name')
    description = request.form.get('description')
    
    if not name:
        flash('Course name is required', 'error')
        return redirect(url_for('admin.course_management'))
    
    if Course.query.filter_by(name=name).first():
        flash('Course with this name already exists', 'error')
        return redirect(url_for('admin.course_management'))
    
    course = Course(
        name=name,
        description=description
    )
    
    db.session.add(course)
    db.session.commit()
    
    flash(f'Course "{name}" created successfully!', 'success')
    return redirect(url_for('admin.course_management'))

@admin_bp.route('/admin/courses/<int:course_id>/edit', methods=['POST'])
@login_required
def edit_course(course_id):
    if current_user.role != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('admin.dashboard'))
    
    course = Course.query.get(course_id)
    if not course:
        flash('Course not found', 'error')
        return redirect(url_for('admin.course_management'))
    
    course.name = request.form.get('name')
    course.description = request.form.get('description')
    
    db.session.commit()
    flash(f'Course "{course.name}" updated successfully!', 'success')
    return redirect(url_for('admin.course_management'))

@admin_bp.route('/admin/courses/<int:course_id>/delete', methods=['POST'])
@login_required
def delete_course(course_id):
    if current_user.role != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('admin.dashboard'))
    
    course = Course.query.get(course_id)
    if not course:
        flash('Course not found', 'error')
        return redirect(url_for('admin.course_management'))
    
    # Check if course has enrollments or assignments
    has_enrollments = Enrollment.query.filter_by(course_id=course_id).first()
    has_assignments = Assignment.query.filter_by(course_id=course_id).first()
    
    if has_enrollments or has_assignments:
        flash('Cannot delete course with existing enrollments or assignments', 'error')
        return redirect(url_for('admin.course_management'))
    
    db.session.delete(course)
    db.session.commit()
    flash(f'Course "{course.name}" deleted successfully!', 'success')
    return redirect(url_for('admin.course_management'))

# ENROLLMENT MANAGEMENT
@admin_bp.route('/admin/enrollments')
@login_required
def enrollment_management():
    if current_user.role != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('auth.login'))
    
    enrollments = Enrollment.query.all()
    students = User.query.filter_by(role='student').all()
    courses = Course.query.all()
    
    return render_template('admin/enrollments.html',
                         enrollments=enrollments,
                         students=students,
                         courses=courses)

@admin_bp.route('/admin/enrollments/enroll', methods=['POST'])
@login_required
def enroll_student():
    if current_user.role != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('admin.dashboard'))
    
    student_id = request.form.get('student_id')
    course_id = request.form.get('course_id')
    
    student = User.query.get(student_id)
    course = Course.query.get(course_id)
    
    if not student or student.role != 'student':
        flash('Invalid student', 'error')
        return redirect(url_for('admin.enrollment_management'))
    
    # Check if already enrolled
    existing = Enrollment.query.filter_by(
        user_id=student_id, 
        course_id=course_id,
        status='active'
    ).first()
    
    if existing:
        flash('Student already enrolled in this course', 'error')
        return redirect(url_for('admin.enrollment_management'))
    
    enrollment = Enrollment(
        user_id=student_id,
        course_id=course_id,
        enrolled_by=current_user.id
    )
    
    db.session.add(enrollment)
    db.session.commit()
    
    flash(f'Student enrolled in {course.name} successfully!', 'success')
    return redirect(url_for('admin.enrollment_management'))

@admin_bp.route('/admin/enrollments/<int:enrollment_id>/drop', methods=['POST'])
@login_required
def drop_enrollment(enrollment_id):
    if current_user.role != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('admin.dashboard'))
    
    enrollment = Enrollment.query.get(enrollment_id)
    if not enrollment:
        flash('Enrollment not found', 'error')
        return redirect(url_for('admin.enrollment_management'))
    
    db.session.delete(enrollment)
    db.session.commit()
    
    flash('Student dropped from course successfully', 'success')
    return redirect(url_for('admin.enrollment_management'))

# SYSTEM ANALYTICS
# TEACHER MANAGEMENT
@admin_bp.route('/admin/create-teacher', methods=['POST'])
@login_required
def create_teacher():
    if current_user.role != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('admin.dashboard'))
    
    username = request.form.get('username')
    name = request.form.get('name')
    password = request.form.get('password')
    
    if User.query.filter_by(username=username).first():
        flash('Username already exists', 'error')
        return redirect(url_for('admin.dashboard'))
    
    teacher = User(
        username=username,
        name=name,
        role='teacher'
    )
    teacher.set_password(password)
    
    db.session.add(teacher)
    db.session.commit()
    
    flash(f'Teacher {name} created successfully!', 'success')
    return redirect(url_for('admin.dashboard'))