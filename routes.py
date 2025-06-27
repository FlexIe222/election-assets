import os
import json
import logging
from datetime import datetime, date
from flask import render_template, request, redirect, url_for, session, flash, jsonify, send_file
from werkzeug.security import generate_password_hash
from app import app, db
from models import User, Bill, Document, Delivery, IncomeRecord, ElectionType, DocumentStatus, DeliveryMethod, UserRole
from utils.pdf_generator import generate_bill_pdf, generate_income_report_pdf
from utils.email_service import send_email_with_attachment
from utils.api_client import check_delivery_status, update_api_status

logger = logging.getLogger(__name__)

def require_login(f):
    """Decorator to require login for protected routes"""
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def get_current_user():
    """Get current logged in user"""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

@app.route('/')
def index():
    page = request.args.get('page', 'login')
    
    if page == 'login':
        return render_template('login.html')
    elif page == 'index':
        return main_menu()
    elif page == 'bill-tracking-by-election-type':
        return bill_tracking()
    elif page == 'my-income':
        return my_income()
    else:
        return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({
                'status': 'error',
                'message': 'กรุณากรอกชื่อผู้ใช้และรหัสผ่าน'
            })
        
        user = User.query.filter_by(username=username, is_active=True).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session.permanent = True
            
            return jsonify({
                'status': 'success',
                'name': user.name,
                'role': user.role.value,
                'authority': user.authority,
                'team': user.team,
                'message': 'เข้าสู่ระบบสำเร็จ'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง'
            })
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'เกิดข้อผิดพลาดในระบบ กรุณาลองใหม่อีกครั้ง'
        })

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/main')
@require_login
def main_menu():
    user = get_current_user()
    return render_template('index.html', user=user)

@app.route('/bill-tracking')
@require_login
def bill_tracking():
    election_type = request.args.get('type', 'by-election')
    user = get_current_user()
    
    # Get bills based on election type
    bills_query = Bill.query.filter_by(election_type=ElectionType(election_type))
    
    # Filter by user role
    if user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        bills_query = bills_query.filter_by(created_by=user.id)
    
    bills = bills_query.order_by(Bill.created_at.desc()).all()
    
    return render_template('bill_tracking.html', 
                         bills=bills, 
                         election_type=election_type,
                         user=user)

@app.route('/my-income')
@require_login
def my_income():
    user = get_current_user()
    
    # Get income records for current user
    income_records = IncomeRecord.query.filter_by(user_id=user.id)\
                                     .order_by(IncomeRecord.period_start.desc()).all()
    
    return render_template('my_income.html', 
                         income_records=income_records, 
                         user=user)

@app.route('/api/bills', methods=['POST'])
@require_login
def create_bill():
    user = get_current_user()
    
    try:
        data = request.get_json()
        
        # Generate bill number
        bill_count = Bill.query.count() + 1
        bill_number = f"BILL-{datetime.now().strftime('%Y%m%d')}-{bill_count:04d}"
        
        bill = Bill(
            bill_number=bill_number,
            election_type=ElectionType(data['election_type']),
            election_name=data['election_name'],
            amount=float(data['amount']),
            due_date=datetime.strptime(data['due_date'], '%Y-%m-%d').date(),
            description=data.get('description', ''),
            recipient_name=data['recipient_name'],
            recipient_address=data['recipient_address'],
            recipient_email=data.get('recipient_email'),
            recipient_phone=data.get('recipient_phone'),
            created_by=user.id
        )
        
        db.session.add(bill)
        db.session.commit()
        
        # Generate PDF document
        pdf_path = generate_bill_pdf(bill)
        
        # Create document record
        doc_number = f"DOC-{datetime.now().strftime('%Y%m%d')}-{bill.id:04d}"
        document = Document(
            document_number=doc_number,
            document_type='invoice',
            title=f"ใบเรียกเก็บเงิน - {bill.election_name}",
            file_path=pdf_path,
            bill_id=bill.id,
            created_by=user.id
        )
        
        db.session.add(document)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'สร้างใบเรียกเก็บเงินสำเร็จ',
            'bill_id': bill.id
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Create bill error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'เกิดข้อผิดพลาดในการสร้างใบเรียกเก็บเงิน'
        })

@app.route('/api/bills/<int:bill_id>/send', methods=['POST'])
@require_login
def send_bill(bill_id):
    user = get_current_user()
    
    try:
        bill = Bill.query.get_or_404(bill_id)
        data = request.get_json()
        method = data.get('method', 'email')
        
        # Check if user has permission
        if user.role not in [UserRole.ADMIN, UserRole.MANAGER] and bill.created_by != user.id:
            return jsonify({
                'status': 'error',
                'message': 'คุณไม่มีสิทธิ์ในการส่งใบเรียกเก็บเงินนี้'
            })
        
        # Get document
        document = Document.query.filter_by(bill_id=bill_id, document_type='invoice').first()
        if not document:
            return jsonify({
                'status': 'error',
                'message': 'ไม่พบเอกสารใบเรียกเก็บเงิน'
            })
        
        # Generate tracking number
        tracking_count = Delivery.query.count() + 1
        tracking_number = f"TRK-{datetime.now().strftime('%Y%m%d')}-{tracking_count:04d}"
        
        # Create delivery record
        delivery = Delivery(
            tracking_number=tracking_number,
            method=DeliveryMethod(method),
            recipient_name=bill.recipient_name,
            recipient_contact=bill.recipient_email if method == 'email' else bill.recipient_phone,
            bill_id=bill.id,
            document_id=document.id,
            sent_at=datetime.utcnow()
        )
        
        db.session.add(delivery)
        
        # Send based on method
        if method == 'email' and bill.recipient_email:
            success = send_email_with_attachment(
                to_email=bill.recipient_email,
                subject=f"ใบเรียกเก็บเงิน - {bill.election_name}",
                body=f"เรียน {bill.recipient_name}\n\nกรุณาชำระเงินตามใบเรียกเก็บเงินที่แนบมา\n\nจำนวนเงิน: {bill.amount:,.2f} บาท\nกำหนดชำระ: {bill.due_date}\n\nขอบคุณครับ",
                attachment_path=document.file_path,
                attachment_name=f"{bill.bill_number}.pdf"
            )
            
            if success:
                delivery.status = DocumentStatus.SENT
                bill.status = DocumentStatus.SENT
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'ไม่สามารถส่งอีเมลได้'
                })
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'ส่งใบเรียกเก็บเงินสำเร็จ',
            'tracking_number': tracking_number
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Send bill error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'เกิดข้อผิดพลาดในการส่งใบเรียกเก็บเงิน'
        })

@app.route('/api/delivery/<tracking_number>/status')
@require_login
def get_delivery_status(tracking_number):
    try:
        delivery = Delivery.query.filter_by(tracking_number=tracking_number).first_or_404()
        
        # Check for real-time status update from external API
        api_status = check_delivery_status(tracking_number)
        if api_status:
            delivery.status = DocumentStatus(api_status['status'])
            if api_status.get('delivered_at'):
                delivery.delivered_at = datetime.fromisoformat(api_status['delivered_at'])
            db.session.commit()
        
        return jsonify({
            'tracking_number': delivery.tracking_number,
            'status': delivery.status.value,
            'method': delivery.method.value,
            'sent_at': delivery.sent_at.isoformat() if delivery.sent_at else None,
            'delivered_at': delivery.delivered_at.isoformat() if delivery.delivered_at else None,
            'recipient_name': delivery.recipient_name,
            'notes': delivery.notes
        })
        
    except Exception as e:
        logger.error(f"Get delivery status error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'ไม่พบข้อมูลการส่งมอบ'
        })

@app.route('/api/income/report')
@require_login
def generate_income_report():
    user = get_current_user()
    
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if start_date and end_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            income_records = IncomeRecord.query.filter_by(user_id=user.id)\
                                             .filter(IncomeRecord.period_start >= start_date)\
                                             .filter(IncomeRecord.period_end <= end_date)\
                                             .all()
        else:
            income_records = IncomeRecord.query.filter_by(user_id=user.id).all()
        
        # Generate PDF report
        pdf_path = generate_income_report_pdf(user, income_records)
        
        return send_file(pdf_path, as_attachment=True, 
                        download_name=f"รายงานรายได้_{user.username}_{datetime.now().strftime('%Y%m%d')}.pdf")
        
    except Exception as e:
        logger.error(f"Generate income report error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'เกิดข้อผิดพลาดในการสร้างรายงาน'
        })

@app.route('/admin/users')
@require_login
def admin_users():
    user = get_current_user()
    if user.role != UserRole.ADMIN:
        flash('คุณไม่มีสิทธิ์เข้าถึงหน้านี้', 'error')
        return redirect(url_for('main_menu'))
    
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users, user=user)

@app.route('/api/admin/users', methods=['POST'])
@require_login
def create_user():
    current_user = get_current_user()
    if current_user.role != UserRole.ADMIN:
        return jsonify({
            'status': 'error',
            'message': 'คุณไม่มีสิทธิ์ในการสร้างผู้ใช้'
        })
    
    try:
        data = request.get_json()
        
        # Check if username already exists
        if User.query.filter_by(username=data['username']).first():
            return jsonify({
                'status': 'error',
                'message': 'ชื่อผู้ใช้นี้มีอยู่แล้ว'
            })
        
        # Check if email already exists
        if data.get('email') and User.query.filter_by(email=data['email']).first():
            return jsonify({
                'status': 'error',
                'message': 'อีเมลนี้มีอยู่แล้ว'
            })
        
        user = User(
            username=data['username'],
            name=data['name'],
            role=UserRole(data['role']),
            authority=data['authority'],
            team=data['team'],
            supervisor_id=data.get('supervisor_id'),
            email=data.get('email'),
            phone=data.get('phone')
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'สร้างผู้ใช้สำเร็จ',
            'user_id': user.id
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Create user error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'เกิดข้อผิดพลาดในการสร้างผู้ใช้'
        })

@app.route('/api/admin/users/bulk', methods=['POST'])
@require_login
def bulk_create_users():
    current_user = get_current_user()
    if current_user.role != UserRole.ADMIN:
        return jsonify({
            'status': 'error',
            'message': 'คุณไม่มีสิทธิ์ในการสร้างผู้ใช้'
        })
    
    try:
        data = request.get_json()
        users_data = data.get('users', [])
        
        created_count = 0
        errors = []
        
        for user_data in users_data:
            try:
                # Check if username already exists
                if User.query.filter_by(username=user_data['username']).first():
                    errors.append(f"ชื่อผู้ใช้ {user_data['username']} มีอยู่แล้ว")
                    continue
                
                # Check if email already exists
                if user_data.get('email') and User.query.filter_by(email=user_data['email']).first():
                    errors.append(f"อีเมล {user_data['email']} มีอยู่แล้ว")
                    continue
                
                user = User(
                    username=user_data['username'],
                    name=user_data['name'],
                    role=UserRole(user_data['role']),
                    authority=user_data['authority'],
                    team=user_data['team'],
                    supervisor_id=user_data.get('supervisor_id'),
                    email=user_data.get('email'),
                    phone=user_data.get('phone')
                )
                user.set_password(user_data.get('password', 'password123'))
                
                db.session.add(user)
                created_count += 1
                
            except Exception as e:
                errors.append(f"ข้อผิดพลาดสำหรับ {user_data.get('username', 'ไม่ระบุ')}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'สร้างผู้ใช้สำเร็จ {created_count} คน',
            'created_count': created_count,
            'errors': errors
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Bulk create users error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'เกิดข้อผิดพลาดในการสร้างผู้ใช้'
        })

@app.route('/api/admin/sheets/import', methods=['POST'])
@require_login
def import_from_sheets():
    current_user = get_current_user()
    if current_user.role != UserRole.ADMIN:
        return jsonify({
            'status': 'error',
            'message': 'คุณไม่มีสิทธิ์ในการนำเข้าข้อมูล'
        })
    
    try:
        data = request.get_json()
        sheets_url = data.get('sheets_url')
        
        if not sheets_url:
            return jsonify({
                'status': 'error',
                'message': 'กรุณาระบุ URL ของ Google Sheets'
            })
        
        # Convert Google Sheets URL to CSV export URL
        if '/edit' in sheets_url:
            sheets_id = sheets_url.split('/d/')[1].split('/')[0]
            csv_url = f"https://docs.google.com/spreadsheets/d/{sheets_id}/export?format=csv&gid=0"
        else:
            return jsonify({
                'status': 'error',
                'message': 'รูปแบบ URL ไม่ถูกต้อง'
            })
        
        # Fetch CSV data
        import requests
        response = requests.get(csv_url)
        response.raise_for_status()
        
        # Parse CSV data
        import csv
        import io
        
        csv_data = response.text
        reader = csv.DictReader(io.StringIO(csv_data))
        
        created_count = 0
        errors = []
        
        for row in reader:
            try:
                if not row.get('username') or not row.get('name'):
                    continue
                
                # Check if username already exists
                if User.query.filter_by(username=row['username']).first():
                    errors.append(f"ชื่อผู้ใช้ {row['username']} มีอยู่แล้ว")
                    continue
                
                user = User(
                    username=row['username'],
                    name=row['name'],
                    role=UserRole(row.get('role', 'staff')),
                    authority=row.get('authority', ''),
                    team=row.get('team', ''),
                    supervisor_id=row.get('supervisor'),
                    email=row.get('email'),
                    phone=row.get('phone')
                )
                user.set_password(row.get('password', row['username']))
                
                db.session.add(user)
                created_count += 1
                
            except Exception as e:
                errors.append(f"ข้อผิดพลาดสำหรับ {row.get('username', 'ไม่ระบุ')}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'นำเข้าผู้ใช้สำเร็จ {created_count} คน',
            'created_count': created_count,
            'errors': errors
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Import from sheets error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'เกิดข้อผิดพลาดในการนำเข้าข้อมูล: {str(e)}'
        })

@app.route('/profile')
@require_login
def user_profile():
    user = get_current_user()
    return render_template('profile.html', user=user)

@app.route('/api/profile/change-password', methods=['POST'])
@require_login
def change_password():
    user = get_current_user()
    
    try:
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        if not user.check_password(current_password):
            return jsonify({
                'status': 'error',
                'message': 'รหัสผ่านปัจจุบันไม่ถูกต้อง'
            })
        
        if new_password != confirm_password:
            return jsonify({
                'status': 'error',
                'message': 'รหัสผ่านใหม่ไม่ตรงกัน'
            })
        
        if len(new_password) < 6:
            return jsonify({
                'status': 'error',
                'message': 'รหัสผ่านต้องมีความยาวอย่างน้อย 6 ตัวอักษร'
            })
        
        user.set_password(new_password)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'เปลี่ยนรหัสผ่านสำเร็จ'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Change password error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'เกิดข้อผิดพลาดในการเปลี่ยนรหัสผ่าน'
        })

# Initialize default admin user - called from app context
def create_default_users():
    try:
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                name='ผู้ดูแลระบบ',
                role=UserRole.ADMIN,
                authority='กรมการปกครอง',
                team='ทีมพัฒนาระบบ',
                email='admin@election.gov.th'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            
        if not User.query.filter_by(username='officer1').first():
            officer = User(
                username='officer1',
                name='เจ้าหน้าที่ 1',
                role=UserRole.OFFICER,
                authority='สำนักงานเลือกตั้งจังหวัด',
                team='ทีมการเงิน',
                email='officer1@election.gov.th'
            )
            officer.set_password('password123')
            db.session.add(officer)
            
        db.session.commit()
        logger.info("Default users created")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating default users: {str(e)}")

# Create default users when app starts
with app.app_context():
    create_default_users()

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500
