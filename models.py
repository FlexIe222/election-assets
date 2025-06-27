from datetime import datetime
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Enum
import enum

class UserRole(enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    OFFICER = "officer"
    STAFF = "staff"
    VIEWER = "viewer"

class ElectionType(enum.Enum):
    BY_ELECTION = "by-election"
    PROJECT_ELECTION = "project-election"

class DocumentStatus(enum.Enum):
    CREATED = "created"
    SENT = "sent"
    DELIVERED = "delivered"
    PAID = "paid"
    CANCELLED = "cancelled"

class DeliveryMethod(enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    POST = "post"
    HAND_DELIVERY = "hand_delivery"

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    role = db.Column(Enum(UserRole), nullable=False, default=UserRole.VIEWER)
    authority = db.Column(db.String(128), nullable=False)  # หน่วยงาน
    team = db.Column(db.String(128), nullable=False)  # ทีม
    supervisor_id = db.Column(db.String(64), nullable=True)  # รหัสหัวหน้า
    email = db.Column(db.String(128), unique=True, nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bills = db.relationship('Bill', backref='created_by_user', lazy=True, foreign_keys='Bill.created_by')
    documents = db.relationship('Document', backref='created_by_user', lazy=True, foreign_keys='Document.created_by')
    income_records = db.relationship('IncomeRecord', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Bill(db.Model):
    __tablename__ = 'bills'
    
    id = db.Column(db.Integer, primary_key=True)
    bill_number = db.Column(db.String(64), unique=True, nullable=False, index=True)
    election_type = db.Column(Enum(ElectionType), nullable=False)
    election_name = db.Column(db.String(256), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text)
    recipient_name = db.Column(db.String(128), nullable=False)
    recipient_address = db.Column(db.Text, nullable=False)
    recipient_email = db.Column(db.String(128))
    recipient_phone = db.Column(db.String(20))
    status = db.Column(Enum(DocumentStatus), default=DocumentStatus.CREATED)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    documents = db.relationship('Document', backref='bill', lazy=True)
    deliveries = db.relationship('Delivery', backref='bill', lazy=True)
    
    def __repr__(self):
        return f'<Bill {self.bill_number}>'

class Document(db.Model):
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    document_number = db.Column(db.String(64), unique=True, nullable=False, index=True)
    document_type = db.Column(db.String(64), nullable=False)  # invoice, receipt, report
    title = db.Column(db.String(256), nullable=False)
    file_path = db.Column(db.String(512))
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(128))
    status = db.Column(Enum(DocumentStatus), default=DocumentStatus.CREATED)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    deliveries = db.relationship('Delivery', backref='document', lazy=True)
    
    def __repr__(self):
        return f'<Document {self.document_number}>'

class Delivery(db.Model):
    __tablename__ = 'deliveries'
    
    id = db.Column(db.Integer, primary_key=True)
    tracking_number = db.Column(db.String(64), unique=True, nullable=False, index=True)
    method = db.Column(Enum(DeliveryMethod), nullable=False)
    recipient_name = db.Column(db.String(128), nullable=False)
    recipient_contact = db.Column(db.String(256), nullable=False)  # email or phone or address
    status = db.Column(Enum(DocumentStatus), default=DocumentStatus.SENT)
    sent_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.id'), nullable=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Delivery {self.tracking_number}>'

class IncomeRecord(db.Model):
    __tablename__ = 'income_records'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    base_salary = db.Column(db.Numeric(10, 2))
    allowances = db.Column(db.Numeric(10, 2))
    overtime = db.Column(db.Numeric(10, 2))
    bonuses = db.Column(db.Numeric(10, 2))
    deductions = db.Column(db.Numeric(10, 2))
    total_income = db.Column(db.Numeric(10, 2), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<IncomeRecord {self.user_id} {self.period_start}-{self.period_end}>'

class ApiLog(db.Model):
    __tablename__ = 'api_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    endpoint = db.Column(db.String(256), nullable=False)
    method = db.Column(db.String(16), nullable=False)
    status_code = db.Column(db.Integer)
    response_time = db.Column(db.Float)
    request_data = db.Column(db.Text)
    response_data = db.Column(db.Text)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ApiLog {self.endpoint} {self.status_code}>'
