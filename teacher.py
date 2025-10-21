from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file, jsonify
from flask_login import login_required, current_user
from models import db, User, Course, Assignment, Enrollment, Submission, LectureMaterial
from datetime import datetime
from utils import save_uploaded_file, save_lecture_material, get_file_type
from notifications import create_bulk_notifications, create_notification
import os

teacher_bp = Blueprint('teacher', __name__)

@teacher_bp.route('/teacher/dashboard')
@login_required
def dashboard():
    if current_user.role != 'teacher':
        flash('Teacher access required', 'error')
        return redirect(url_for('auth.login'))
    
    assignments = Assignment.query.filter_by(teacher_id=current_user.id).all()
    courses = Course.query.all()
    
    # Calculate grading statistics
    total_submissions = 0
    pending_grading = 0
    graded_count = 0
    
    for assignment in assignments:
        submissions = Submission.query.filter_by(assignment_id=assignment.id).all()
        total_submissions += len(submissions)
        pending_grading += len([s for s in submissions if s.status != 'graded'])
        graded_count += len([s for s in submissions if s.status == 'graded'])
    
    return render_template('teacher/dashboard.html',
                         assignments=assignments,
                         courses=courses,
                         total_submissions=total_submissions,
                         pending_grading=pending_grading,
                         graded_count=graded_count)

@teacher_bp.route('/teacher/create-assignment', methods=['POST'])
@login_required
def create_assignment():
    if current_user.role != 'teacher':
        flash('Teacher access required', 'error')
        return redirect(url_for('auth.login'))
    
    title = request.form.get('title')
    description = request.form.get('description')
    due_date = request.form.get('due_date')
    course_id = request.form.get('course_id')
    max_marks = request.form.get('max_marks', 100)
    
    try:
        due_date = datetime.strptime(due_date, '%Y-%m-%d')
    except ValueError:
        flash('Invalid date format', 'error')
        return redirect(url_for('teacher.dashboard'))
    
    assignment = Assignment(
        title=title,
        description=description,
        due_date=due_date,
        course_id=course_id,
        teacher_id=current_user.id,
        max_marks=max_marks
    )
    
    db.session.add(assignment)
    db.session.commit()
    
    # NOTIFICATION: Notify enrolled students about new assignment
    enrollments = Enrollment.query.filter_by(
        course_id=course_id, 
        status='active'
    ).all()
    
    student_ids = [enrollment.user_id for enrollment in enrollments]
    
    if student_ids:
        create_bulk_notifications(
            user_ids=student_ids,
            title="New Assignment Posted",
            message=f"New assignment '{title}' has been posted for {assignment.course.name}",
            notification_type="assignment",
            related_id=assignment.id
        )
    
    flash(f'Assignment "{title}" created successfully!', 'success')
    return redirect(url_for('teacher.dashboard'))

@teacher_bp.route('/teacher/assignments')
@login_required
def assignments():
    if current_user.role != 'teacher':
        flash('Teacher access required', 'error')
        return redirect(url_for('auth.login'))
    
    assignments = Assignment.query.filter_by(teacher_id=current_user.id).all()
    return render_template('teacher/assignments.html', assignments=assignments)

@teacher_bp.route('/teacher/course-students/<int:course_id>')
@login_required
def course_students(course_id):
    if current_user.role != 'teacher':
        flash('Teacher access required', 'error')
        return redirect(url_for('auth.login'))
    
    enrollments = Enrollment.query.filter_by(
        course_id=course_id, 
        status='active'
    ).all()
    
    students = [enrollment.student for enrollment in enrollments]
    course = Course.query.get(course_id)
    
    return render_template('teacher/course_students.html',
                         students=students,
                         course=course)

@teacher_bp.route('/teacher/submissions/<int:assignment_id>')
@login_required
def view_submissions(assignment_id):
    if current_user.role != 'teacher':
        flash('Teacher access required', 'error')
        return redirect(url_for('auth.login'))
    
    assignment = Assignment.query.get(assignment_id)
    
    if not assignment or assignment.teacher_id != current_user.id:
        flash('Assignment not found', 'error')
        return redirect(url_for('teacher.assignments'))
    
    submissions = Submission.query.filter_by(assignment_id=assignment_id).all()
    
    # Calculate assignment statistics
    total_students = len(Enrollment.query.filter_by(course_id=assignment.course_id, status='active').all())
    submitted_count = len(submissions)
    graded_count = len([s for s in submissions if s.status == 'graded'])
    average_marks = 0
    
    graded_submissions = [s for s in submissions if s.marks is not None]
    if graded_submissions:
        average_marks = sum(s.marks for s in graded_submissions) / len(graded_submissions)
    
    return render_template('teacher/submissions.html',
                         assignment=assignment,
                         submissions=submissions,
                         total_students=total_students,
                         submitted_count=submitted_count,
                         graded_count=graded_count,
                         average_marks=round(average_marks, 1))

@teacher_bp.route('/teacher/download-submission/<int:submission_id>')
@login_required
def download_submission(submission_id):
    """Teacher downloads student submission"""
    submission = Submission.query.get(submission_id)
    
    if not submission:
        flash('Submission not found', 'error')
        return redirect(url_for('teacher.assignments'))
    
    # Verify teacher owns the assignment
    assignment = Assignment.query.get(submission.assignment_id)
    if not assignment or assignment.teacher_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('teacher.assignments'))
    
    if not submission.file_path:
        flash('No file attached to this submission', 'error')
        return redirect(url_for('teacher.view_submissions', assignment_id=submission.assignment_id))
    
    # Check if file actually exists
    file_path = os.path.join('static/uploads', submission.file_path)
    if not os.path.exists(file_path):
        flash('File not found on server', 'error')
        return redirect(url_for('teacher.view_submissions', assignment_id=submission.assignment_id))
    
    # Get student and assignment info for filename
    student = User.query.get(submission.student_id)
    
    # Create a clean filename
    original_extension = submission.file_path.split('.')[-1]
    clean_assignment_name = "".join(c for c in assignment.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
    clean_student_name = "".join(c for c in student.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    
    filename = f"{clean_student_name}_{clean_assignment_name}.{original_extension}"
    
    try:
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Error downloading file: {str(e)}', 'error')
        return redirect(url_for('teacher.view_submissions', assignment_id=submission.assignment_id))

@teacher_bp.route('/teacher/grade-submission/<int:submission_id>', methods=['POST'])
@login_required
def grade_submission(submission_id):
    if current_user.role != 'teacher':
        flash('Teacher access required', 'error')
        return redirect(url_for('auth.login'))
    
    submission = Submission.query.get(submission_id)
    
    if not submission:
        flash('Submission not found', 'error')
        return redirect(url_for('teacher.assignments'))
    
    assignment = Assignment.query.get(submission.assignment_id)
    if assignment.teacher_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('teacher.assignments'))
    
    marks = request.form.get('marks')
    feedback = request.form.get('feedback', '').strip()
    
    try:
        marks_float = float(marks)
        if marks_float < 0 or marks_float > assignment.max_marks:
            flash(f'Marks must be between 0 and {assignment.max_marks}', 'error')
            return redirect(url_for('teacher.view_submissions', assignment_id=submission.assignment_id))
        
        submission.marks = marks_float
        submission.feedback = feedback
        submission.status = 'graded'
        
        db.session.commit()
        
        # NOTIFICATION: Notify student about grade
        create_notification(
            user_id=submission.student_id,
            title="Assignment Graded",
            message=f"Your submission for '{assignment.title}' has been graded: {marks_float}/{assignment.max_marks}",
            notification_type="grade",
            related_id=submission.id
        )
        
        flash('Submission graded successfully!', 'success')
    except ValueError:
        flash('Please enter valid marks', 'error')
    
    return redirect(url_for('teacher.view_submissions', assignment_id=submission.assignment_id))

@teacher_bp.route('/teacher/gradebook/<int:course_id>')
@login_required
def gradebook(course_id):
    if current_user.role != 'teacher':
        flash('Teacher access required', 'error')
        return redirect(url_for('auth.login'))
    
    course = Course.query.get(course_id)
    if not course:
        flash('Course not found', 'error')
        return redirect(url_for('teacher.dashboard'))
    
    # Get all assignments for this course by current teacher
    assignments = Assignment.query.filter_by(
        course_id=course_id,
        teacher_id=current_user.id
    ).all()
    
    # Get all enrolled students
    enrollments = Enrollment.query.filter_by(
        course_id=course_id,
        status='active'
    ).all()
    students = [enrollment.student for enrollment in enrollments]
    
    # Build gradebook data
    gradebook_data = []
    for student in students:
        student_grades = []
        total_marks = 0
        total_possible = 0
        graded_assignments = 0
        
        for assignment in assignments:
            submission = Submission.query.filter_by(
                assignment_id=assignment.id,
                student_id=student.id
            ).first()
            
            if submission and submission.marks is not None:
                student_grades.append({
                    'assignment': assignment,
                    'submission': submission,
                    'marks': submission.marks,
                    'percentage': (submission.marks / assignment.max_marks) * 100
                })
                total_marks += submission.marks
                total_possible += assignment.max_marks
                graded_assignments += 1
            else:
                student_grades.append({
                    'assignment': assignment,
                    'submission': submission,
                    'marks': None,
                    'percentage': None
                })
        
        average = (total_marks / total_possible * 100) if total_possible > 0 else 0
        
        gradebook_data.append({
            'student': student,
            'grades': student_grades,
            'total_marks': total_marks,
            'total_possible': total_possible,
            'average': round(average, 1),
            'graded_count': graded_assignments
        })
    
    return render_template('teacher/gradebook.html',
                         course=course,
                         assignments=assignments,
                         gradebook_data=gradebook_data)

@teacher_bp.route('/teacher/bulk-grade/<int:assignment_id>', methods=['POST'])
@login_required
def bulk_grade(assignment_id):
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'error': 'Access denied'})
    
    assignment = Assignment.query.get(assignment_id)
    if not assignment or assignment.teacher_id != current_user.id:
        return jsonify({'success': False, 'error': 'Assignment not found'})
    
    try:
        data = request.get_json()
        for grade_data in data.get('grades', []):
            submission = Submission.query.get(grade_data['submission_id'])
            if submission and submission.assignment_id == assignment_id:
                submission.marks = float(grade_data['marks'])
                submission.feedback = grade_data.get('feedback', '')
                submission.status = 'graded'
                
                # NOTIFICATION: Notify student about grade
                create_notification(
                    user_id=submission.student_id,
                    title="Assignment Graded",
                    message=f"Your submission for '{assignment.title}' has been graded: {submission.marks}/{assignment.max_marks}",
                    notification_type="grade",
                    related_id=submission.id
                )
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Grades updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

# LECTURE MATERIALS ROUTES

@teacher_bp.route('/teacher/course-materials/<int:course_id>')
@login_required
def course_materials(course_id):
    if current_user.role != 'teacher':
        flash('Teacher access required', 'error')
        return redirect(url_for('auth.login'))
    
    course = Course.query.get(course_id)
    if not course:
        flash('Course not found', 'error')
        return redirect(url_for('teacher.dashboard'))
    
    # Verify teacher owns this course (through assignments)
    teacher_assignments = Assignment.query.filter_by(
        teacher_id=current_user.id, 
        course_id=course_id
    ).first()
    
    if not teacher_assignments:
        flash('You do not teach this course', 'error')
        return redirect(url_for('teacher.dashboard'))
    
    # Get all materials for this course
    materials = LectureMaterial.query.filter_by(
        course_id=course_id
    ).order_by(LectureMaterial.week_number, LectureMaterial.created_at.desc()).all()
    
    return render_template('teacher/course_materials.html',
                         course=course,
                         materials=materials)

@teacher_bp.route('/teacher/upload-material/<int:course_id>', methods=['GET', 'POST'])
@login_required
def upload_material(course_id):
    if current_user.role != 'teacher':
        flash('Teacher access required', 'error')
        return redirect(url_for('auth.login'))
    
    course = Course.query.get(course_id)
    if not course:
        flash('Course not found', 'error')
        return redirect(url_for('teacher.dashboard'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        week_number = request.form.get('week_number')
        
        if not title:
            flash('Title is required', 'error')
            return render_template('teacher/upload_material.html', course=course)
        
        # Handle file upload
        file_path = None
        file_type = 'link'  # Default for external links
        
        if 'material_file' in request.files:
            file = request.files['material_file']
            if file and file.filename:
                file_path = save_lecture_material(file)
                if not file_path:
                    flash('Invalid file type', 'error')
                    return render_template('teacher/upload_material.html', course=course)
                file_type = get_file_type(file.filename)
        
        # External link
        external_link = request.form.get('external_link')
        if external_link and not file_path:
            file_path = external_link
            file_type = 'link'
        
        if not file_path:
            flash('Please upload a file or provide an external link', 'error')
            return render_template('teacher/upload_material.html', course=course)
        
        # Create material
        material = LectureMaterial(
            title=title,
            description=description,
            file_path=file_path,
            file_type=file_type,
            week_number=week_number if week_number else None,
            course_id=course_id,
            teacher_id=current_user.id
        )
        
        db.session.add(material)
        db.session.commit()
        
        # NOTIFICATION: Notify students about new material
        enrollments = Enrollment.query.filter_by(
            course_id=course_id, 
            status='active'
        ).all()
        
        student_ids = [enrollment.user_id for enrollment in enrollments]
        
        if student_ids:
            create_bulk_notifications(
                user_ids=student_ids,
                title="New Lecture Material",
                message=f"New material '{title}' has been added to {course.name}",
                notification_type="material",
                related_id=material.id
            )
        
        flash(f'Material "{title}" uploaded successfully!', 'success')
        return redirect(url_for('teacher.course_materials', course_id=course_id))
    
    return render_template('teacher/upload_material.html', course=course)

@teacher_bp.route('/teacher/delete-material/<int:material_id>', methods=['POST'])
@login_required
def delete_material(material_id):
    if current_user.role != 'teacher':
        flash('Teacher access required', 'error')
        return redirect(url_for('auth.login'))
    
    material = LectureMaterial.query.get(material_id)
    if not material or material.teacher_id != current_user.id:
        flash('Material not found', 'error')
        return redirect(url_for('teacher.dashboard'))
    
    course_id = material.course_id
    db.session.delete(material)
    db.session.commit()
    
    flash('Material deleted successfully', 'success')
    return redirect(url_for('teacher.course_materials', course_id=course_id))

@teacher_bp.route('/teacher/download-material/<int:material_id>')
@login_required
def download_material(material_id):
    """Teacher downloads material (for verification)"""
    material = LectureMaterial.query.get(material_id)
    
    if not material or material.teacher_id != current_user.id:
        flash('Material not found', 'error')
        return redirect(url_for('teacher.dashboard'))
    
    if material.file_type == 'link':
        flash('Cannot download external links', 'error')
        return redirect(url_for('teacher.course_materials', course_id=material.course_id))
    
    file_path = os.path.join('static/uploads', material.file_path)
    if not os.path.exists(file_path):
        flash('File not found on server', 'error')
        return redirect(url_for('teacher.course_materials', course_id=material.course_id))
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=f"{material.title}.{material.file_path.split('.')[-1]}"
    )