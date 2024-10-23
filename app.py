from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# إعداد قاعدة البيانات SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///appointments.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'a_very_secret_key_12345'

db = SQLAlchemy(app)

# إعداد البريد الإلكتروني باستخدام Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'dgerges634@gmail.com'
app.config['MAIL_PASSWORD'] = 'rqrx dmuo gcyz lqzz'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

mail = Mail(app)

# إنشاء نماذج (Models) لقاعدة البيانات
class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    schedules = db.relationship('DoctorSchedule', backref='doctor', lazy=True)

class DoctorSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    day = db.Column(db.String(10), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    patient_name = db.Column(db.String(100), nullable=False)
    patient_phone = db.Column(db.String(20), nullable=False)
    appointment_start_time = db.Column(db.Time, nullable=False)
    appointment_end_time = db.Column(db.Time, nullable=False)
    description = db.Column(db.String(200))
    day = db.Column(db.String(20), nullable=False)
    week_offset = db.Column(db.Integer, nullable=True)
    appointment_date = db.Column(db.Date, nullable=False)  #

def is_time_conflict(start_time, end_time, day, booked_slots):
    for slot in booked_slots:
        if slot['day'] == day:
            booked_start = slot['start_time']
            booked_end = slot['end_time']

            if start_time < booked_end and end_time > booked_start:
                return True
    return False

def get_available_slots(doctor_id, week_offset):
    doctor_schedules = DoctorSchedule.query.filter_by(doctor_id=doctor_id).all()
    booked_appointments = Appointment.query.filter_by(doctor_id=doctor_id, week_offset=week_offset).all()

    booked_slots = [{
        'day': appointment.day,
        'start_time': appointment.appointment_start_time,
        'end_time': appointment.appointment_end_time
    } for appointment in booked_appointments]

    available_slots = []
    days_mapping = {
        "Sunday": 6,
        "Monday": 0,
        "Tuesday": 1,
        "Wednesday": 2,
        "Thursday": 3,
        "Friday": 4,
        "Saturday": 5
    }

    today = datetime.today()
    current_week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)

    for schedule in doctor_schedules:
        day_name = schedule.day
        if day_name in days_mapping:
            day_offset = (days_mapping[day_name] - current_week_start.weekday()) % 7
            appointment_day = current_week_start + timedelta(days=day_offset)

            # تجاهل الأيام الماضية في الأسبوع الحالي فقط للأسبوع 0
            if week_offset == 0 and appointment_day <= today:
                continue

            start_time = datetime.combine(appointment_day, schedule.start_time)
            end_time = datetime.combine(appointment_day, schedule.end_time)

            # جلب فترات الساعة
            current_time = start_time
            while current_time + timedelta(hours=1) <= end_time:
                hour_end_time = current_time + timedelta(hours=1)

                if not is_time_conflict(current_time.time(), hour_end_time.time(), schedule.day, booked_slots):
                    available_slots.append({
                        'day': schedule.day,
                        'start_time': current_time.strftime('%I:%M %p'),
                        'end_time': hour_end_time.strftime('%I:%M %p'),
                      'full_time_slot': f"{schedule.day} - {appointment_day.strftime('%d/%m/%Y')} - {current_time.strftime('%I:%M %p')} - {hour_end_time.strftime('%I:%M %p')}",
                        'ull_time_slot': f" {appointment_day.strftime('%d/%m/%Y')} ",

                        'duration': 'ساعة'
                    })

                current_time = hour_end_time

            # جلب فترات النصف ساعة
            current_time = start_time
            while current_time + timedelta(minutes=30) <= end_time:
                half_end_time = current_time + timedelta(minutes=30)

                if not is_time_conflict(current_time.time(), half_end_time.time(), schedule.day, booked_slots):
                    available_slots.append({
                        'day': schedule.day,
                        'start_time': current_time.strftime('%I:%M %p'),
                        'end_time': half_end_time.strftime('%I:%M %p'),
                        'full_time_slot': f" {appointment_day.strftime('%d/%m/%Y')} - {current_time.strftime('%I:%M %p')} - {half_end_time.strftime('%I:%M %p')}",
                        'ull_time_slot': f" {appointment_day.strftime('%d/%m/%Y')} ",
                        'duration': 'نصف ساعة'
                    })

                current_time = half_end_time

    # ترتيب المواعيد بحيث تظهر مواعيد الساعة أولاً ثم مواعيد النصف ساعة
    available_slots = sorted(available_slots, key=lambda x: x['duration'], reverse=True)
    
    return available_slots


@app.route('/book/doctor<int:doctor_id>', methods=['GET', 'POST'])
def book(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)

    # جلب الأسبوع من المتغيرات المطلوبة
    week_offset = request.args.get('week', 0, type=int)  # استخدم 0 كقيمة افتراضية
    available_slots = get_available_slots(doctor_id, week_offset)

    if request.method == 'POST':
        patient_name = request.form['name']
        patient_phone = request.form['phone']
        description = request.form['description']
        selected_slot = request.form['time_day']

        # تأكد أن البيانات ليست فارغة
        if not selected_slot:
            flash('يرجى اختيار موعد صحيح.')
            return redirect(url_for('book', doctor_id=doctor_id, week=week_offset))

        try:
            day, start_time_str, end_time_str, full_time_slot = selected_slot.split('|')
            time_parts = full_time_slot.split(' - ')
            if len(time_parts) < 3:
               flash('حدث خطأ في معالجة الموعد المحدد.')
               return redirect(url_for('book', doctor_id=doctor_id, week=week_offset))
            date_part = time_parts[1] 
            appointment_date = datetime.strptime(date_part.strip(), '%d/%m/%Y').date()
            appointment_start_time = datetime.strptime(start_time_str.strip(), '%I:%M %p').time()
            appointment_end_time = datetime.strptime(end_time_str.strip(), '%I:%M %p').time()

        except ValueError as e:
            flash(f"خطأ في إدخال البيانات: {str(e)}")
            return redirect(url_for('book', doctor_id=doctor_id, week=week_offset))

        # حفظ الحجز في قاعدة البيانات
        new_appointment = Appointment(
            doctor_id=doctor_id,
            patient_name=patient_name,
            patient_phone=patient_phone,
            appointment_start_time=appointment_start_time,
            appointment_end_time=appointment_end_time,
            description=description,
            day=day,
            week_offset=week_offset,
            appointment_date=appointment_date  # إضافة التاريخ للحجز
        )
        db.session.add(new_appointment)
        db.session.commit()

        # إرسال البريد الإلكتروني للطبيب
        if doctor.email:
            msg = Message('موعد جديد', sender=app.config['MAIL_USERNAME'], recipients=[doctor.email])
            msg.body = (
                f'تم حجز موعد جديد:\n\n'
                f'الاسم: {patient_name}\n'
                f'رقم الهاتف: {patient_phone}\n'
                f'اليوم: {day}\n'
                f'التاريخ: {appointment_date}\n'
                f'الوقت: {appointment_start_time} - {appointment_end_time}\n'
                f'الوصف: {description}'
            )
            mail.send(msg)

        flash('تم الحجز بنجاح لتأكيد الحجز تواصل علي الرقم الطبيب في بطاقة الطبيب لدفع تمن الجلسة ')
        return redirect(url_for('book', doctor_id=doctor_id, week=week_offset))

    # عرض رسالة عدم توفر مواعيد مباشرة في القالب بدلاً من flash
    no_slots_message = 'لا توجد مواعيد متاحة هذا الأسبوع.' if not available_slots else ''

    return render_template('book.html', doctor=doctor, available_slots=available_slots, week_offset=week_offset, doctor_id=doctor_id, no_slots_message=no_slots_message)

@app.route('/add_schedule', methods=['GET', 'POST'])
def add_schedule():
    if request.method == 'POST':
        doctor_id = request.form['doctor_id']
        day = request.form['day']
        start_time = request.form['start_time']
        end_time = request.form['end_time']

        start_time = datetime.strptime(start_time, '%H:%M').time()
        end_time = datetime.strptime(end_time, '%H:%M').time()

        new_schedule = DoctorSchedule(doctor_id=doctor_id, day=day, start_time=start_time, end_time=end_time)
        db.session.add(new_schedule)
        db.session.commit()

        flash('تم إضافة المواعيد للطبيب.')
        return redirect(url_for('add_schedule'))

    doctors = Doctor.query.all()
    return render_template('add_schedule.html', doctors=doctors)
@app.route('/doctor/<int:doctor_id>/appointments')
def view_appointments(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    appointments = Appointment.query.filter_by(doctor_id=doctor_id).all()

    return render_template('view_appointments.html', doctor=doctor, appointments=appointments)

@app.route("/" )
def homepage():
  return render_template("index.html")


@app.route("/app.html" )
def appp():
  return render_template("app.html")

@app.route("/doctor-info.html" )
def docoter_info():
  return render_template("doctor-info.html")

@app.route("/treatment.html" )
def treatment():
  return render_template("treatment.html")

@app.route('/delete_appointment/<int:appointment_id>', methods=['POST'])
def delete_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)

    # حذف الموعد من قاعدة البيانات
    db.session.delete(appointment)
    db.session.commit()


    return redirect(url_for('view_appointments', doctor_id=appointment.doctor_id))
if __name__ == '__main__':

    with app.app_context(): 
        db.create_all()  # أنشئ الجداول الجديدة
    app.run(debug=True)
