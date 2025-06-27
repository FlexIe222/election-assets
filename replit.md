# Thai Local Election System

## Overview

This is a Flask-based web application for managing Thai local elections, specifically designed to track billing and payment collection for election-related services. The system handles both by-elections and project elections, providing comprehensive document management, delivery tracking, and income reporting capabilities.

The application is built with Flask as the web framework, SQLAlchemy for database operations, and includes PDF generation, email services, and external API integrations for delivery tracking and payment processing.

## System Architecture

### Backend Architecture
- **Framework**: Flask 3.1.1 with Python 3.11
- **Database ORM**: SQLAlchemy 2.0.41 with Flask-SQLAlchemy 3.1.1
- **Database**: PostgreSQL (configured via environment variables)
- **WSGI Server**: Gunicorn 23.0.0 for production deployment
- **Session Management**: Flask sessions with secure secret key
- **Authentication**: Custom session-based authentication with role-based access control

### Frontend Architecture
- **Template Engine**: Jinja2 (Flask's default)
- **CSS Framework**: Bootstrap 5.1.3
- **Icons**: Font Awesome 6.0.0
- **Typography**: Custom Thai font (TH SarabunPSK) loaded from external CDN
- **JavaScript**: Vanilla JavaScript with AJAX functionality

### Database Schema
The application uses an enum-based status system with the following key models:
- **User**: Role-based user management (Admin, Manager, Officer, Viewer)
- **Bill**: Election billing records
- **Document**: Document management with status tracking
- **Delivery**: Delivery tracking with multiple methods (Email, SMS, Post, Hand delivery)
- **IncomeRecord**: Financial tracking and reporting

## Key Components

### Authentication & Authorization
- Role-based access control with four user levels
- Session-based authentication using Flask sessions
- Decorator-based route protection (`@require_login`)
- User context management with `get_current_user()`

### Document Management
- PDF generation using ReportLab with Thai font support
- Document status tracking (Created, Sent, Delivered, Paid, Cancelled)
- File attachment handling for email delivery

### Email Service
- SMTP-based email delivery with attachment support
- Configurable email settings via environment variables
- Support for CC/BCC recipients
- Gmail SMTP integration by default

### External API Integration
- Delivery tracking integration with Thailand Post API
- SMS service integration
- Payment gateway integration with Bank of Thailand API
- Retry logic and error handling for API calls
- Request logging and monitoring

### PDF Generation
- Thai language support with custom font loading
- Bill generation with formatted layouts
- Income report generation
- ReportLab-based document creation

## Data Flow

1. **User Authentication**: Users log in through session-based authentication
2. **Bill Creation**: Authorized users create bills for election services
3. **Document Generation**: System generates PDF documents for bills
4. **Delivery Processing**: Documents are sent via email, SMS, or physical delivery
5. **Status Tracking**: External APIs provide delivery status updates
6. **Payment Processing**: Payment confirmations update bill status
7. **Income Reporting**: System generates financial reports for users

## External Dependencies

### Third-party Services
- **Thailand Post API**: For delivery tracking and postal services
- **SMS Gateway**: Government SMS API for notifications
- **Bank of Thailand API**: Payment processing and verification
- **Email SMTP**: Gmail or custom SMTP server for email delivery

### Key Python Packages
- `flask` (3.1.1): Web application framework
- `flask-sqlalchemy` (3.1.1): Database ORM integration
- `psycopg2-binary` (2.9.10): PostgreSQL database adapter
- `reportlab` (4.4.2): PDF generation library
- `gunicorn` (23.0.0): WSGI HTTP server for production
- `flask-login` (0.6.3): User session management
- `email-validator` (2.2.0): Email validation utilities
- `requests`: HTTP library for API integrations

### External Assets
- Thai font (TH SarabunPSK) from GitHub repository
- Background images and icons from external CDNs
- Bootstrap and Font Awesome from CDNs

## Deployment Strategy

### Production Configuration
- **Server**: Gunicorn with auto-scaling deployment target
- **Process Management**: Parallel workflow execution
- **Port Configuration**: Application runs on port 5000
- **Proxy Support**: ProxyFix middleware for reverse proxy compatibility
- **Environment Variables**: Database URL, API keys, and email credentials

### Database Management
- Connection pooling with 300-second recycle time
- Pre-ping enabled for connection health checks
- Automatic table creation on application startup
- PostgreSQL-specific optimizations

### Security Considerations
- Environment-based secret key management
- SQL injection prevention through SQLAlchemy ORM
- CSRF protection through session management
- Role-based access control implementation

## Recent Changes

### June 27, 2025
- Created complete Thai local election billing system with Flask
- Implemented user authentication with role-based access control (Admin, Manager, Officer, Viewer)
- Added bill tracking functionality for by-elections and project-elections
- Built document generation system with PDF creation using Thai fonts
- Integrated delivery tracking with multiple methods (Email, SMS, Post, Hand delivery)
- Added external API integration for real-time status updates
- Created income reporting system with PDF generation
- Added admin user management interface with bulk import functionality
- System supports Google Sheets data import for user creation

### Key Features Completed
- Login system with session management
- Bill creation and tracking with status management
- PDF document generation with Thai language support
- Email service integration for document delivery
- Real-time delivery status tracking via external APIs
- Income report generation for users
- Admin panel for user management
- Bulk user import from spreadsheet data

## User Preferences

Preferred communication style: Simple, everyday language.
Data approach: Use authentic data sources, never mock data.
UI Language: Thai language interface with proper font support.