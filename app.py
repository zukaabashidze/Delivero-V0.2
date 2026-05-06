from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import requests
import telebot
from datetime import datetime
from threading import Thread

app = Flask(__name__)
app.config['SECRET_KEY'] = 'zukasmtavaripaneli'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'delivery.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

TELEGRAM_TOKEN = "8722774055:AAGrs56BqrvegJx8BD3Pxy64DtPUkJ12owA"
TELEGRAM_CHAT_ID = "6510438875" 
bot = telebot.TeleBot(TELEGRAM_TOKEN)

def send_telegram_notification(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print(f"Telegram error: {e}")

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(100))
    role = db.Column(db.String(20), default='user') 
    applications = db.relationship('Application', backref='applicant', lazy=True)
    assigned_orders = db.relationship('Order', backref='courier', lazy=True)

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    pid = db.Column(db.String(11))
    phone = db.Column(db.String(20))
    location = db.Column(db.String(100))
    status = db.Column(db.String(20), default='განხილვაშია')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(100))
    customer_name = db.Column(db.String(100))
    customer_phone = db.Column(db.String(20))
    city = db.Column(db.String(50))      
    address = db.Column(db.String(200))
    weight = db.Column(db.String(20))
    price = db.Column(db.Float)            
    status = db.Column(db.String(20), default='მზად არის')
    courier_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    courier_handed_at = db.Column(db.DateTime) 
    estimated_delivery = db.Column(db.String(50)) 

@login_manager.user_loader
def load_user(id): 
    return db.session.get(User, int(id))

@app.route('/')
def index(): 
    return render_template('index.html')

@app.route('/about')
def about(): 
    return render_template('about.html')

@app.route('/apply', methods=['GET', 'POST'])
def apply():
    if request.method == 'POST':

        full_name = request.form.get('full_name', '').strip()
        id_number = request.form.get('id_number', '').strip()
        phone = request.form.get('phone', '').strip()
        city = request.form.get('city', '').strip()

        if not full_name or len(id_number) != 11 or len(phone) < 9:
            flash('გთხოვთ შეავსოთ ფორმა წესების დაცვით!', 'danger')
            return redirect(url_for('apply'))

        new_app = Application(
            name=full_name,
            pid=id_number,
            phone=phone,
            location=city,
            user_id=current_user.id if current_user.is_authenticated else None
        )
        db.session.add(new_app)
        db.session.commit()

        msg = (f"🚴 <b>ახალი კურიერის განაცხადი!</b>\n"
               f"───────────────\n"
               f"👤 <b>სახელი:</b> {full_name or '❌'}\n"
               f"🆔 <b>პირადი ნომერი:</b> <code>{id_number or '❌'}</code>\n"
               f"📞 <b>ტელეფონი:</b> {phone or '❌'}\n"
               f"🏙️ <b>ქალაქი:</b> {city or '❌'}\n"
               f"───────────────")
        send_telegram_notification(msg)

        flash('თქვენი განაცხადი წარმატებით გაიგზავნა!', 'success')
        return redirect(url_for('index'))
    
    return render_template('apply.html')
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        msg = (f"📩 <b>ახალი შეტყობინება კონტაქტიდან!</b>\n"
               f"───────────────\n"
               f"👤 <b>სახელი:</b> {name}\n"
               f"📧 <b>Email:</b> <code>{email}</code>\n"
               f"📝 <b>მესიჯი:</b>\n<i>{message}</i>\n"
               f"───────────────")
        send_telegram_notification(msg)
        flash('შეტყობინება წარმატებით გაიგზავნა!', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/track', methods=['GET', 'POST'])
def track():
    order = None
    error = False
    if request.method == 'POST':
        order_id = request.form.get('order_id')
        if order_id:
            try:
                order = db.session.get(Order, int(order_id))
                if not order:
                    error = True
            except ValueError:
                error = True
        else:
            error = True
    return render_template('track.html', order=order, error=error)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').lower().strip()
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('სახელი დაკავებულია!', 'danger')
            return redirect(url_for('register'))
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        role = 'admin' if username == 'zuka abashidze' else 'user'
        new_user = User(username=username, password=hashed_pw, role=role)
        db.session.add(new_user)
        db.session.commit()
        
        msg = (f"👤 <b>ახალი მომხმარებელი დარეგისტრირდა!</b>\n"
               f"───────────────\n"
               f"🆔 <b>იუზერი:</b> <code>{username}</code>\n"
               f"🎭 <b>როლი:</b> <code>{role}</code>\n"
               f"───────────────")
        send_telegram_notification(msg)
        flash('რეგისტრაცია წარმატებულია!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username').lower().strip()).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('არასწორი მონაცემები!', 'danger')
    return render_template('login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')

        msg = (f"🔑 <b>პაროლის აღდგენის მოთხოვნა!</b>\n"
               f"───────────────\n"
               f"👤 <b>მომხმარებელი:</b> <code>{username}</code>\n"
               f"📧 <b>Gmail:</b> {email}\n"
               f"───────────────")
        send_telegram_notification(msg)
        
        flash('მოთხოვნა გაიგზავნა! ადმინისტრაცია მალე დაგიკავშირდებათ.', 'info')
        return redirect(url_for('login'))
    
    return render_template('forgot_password.html')

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin' or current_user.username == 'zuka abashidze':
        return redirect(url_for('admin'))
    if current_user.role == 'courier':
        orders = Order.query.filter_by(courier_id=current_user.id).all()
        return render_template('courier_dashboard.html', orders=orders)
    return render_template('user_dashboard.html')

@app.route('/privacy-policy')
def privacy():
    return render_template('privacy.html')


@app.route('/business')
def business():
    return render_template('business.html')


@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin' and current_user.username != 'zuka abashidze': 
        return redirect(url_for('dashboard'))
    
    apps = Application.query.all()
    couriers = User.query.filter_by(role='courier').all()
    users = User.query.filter_by(role='user').all() 
    orders = Order.query.order_by(Order.created_at.desc()).all()
  
    return render_template('admin.html', 
                           apps=apps, 
                           couriers=couriers, 
                           users=users,  
                           orders=orders, 
                           total_orders=len(orders))

@app.route('/create_order', methods=['POST'])
@login_required
def create_order():
    if current_user.role != 'admin' and current_user.username != 'zuka abashidze': 
        return redirect(url_for('dashboard'))
    
    new_order = Order(
        item_name=request.form.get('item_name'),
        customer_name=request.form.get('customer_name'),
        customer_phone=request.form.get('customer_phone'),
        city=request.form.get('city'),
        address=request.form.get('address'),
        weight=request.form.get('weight'),
        price=request.form.get('price'),
        courier_id=request.form.get('courier_id'),
        estimated_delivery=request.form.get('estimated_delivery')
    )
    db.session.add(new_order)
    db.session.commit()
    
    courier = db.session.get(User, new_order.courier_id)
    msg = (f"📦 <b>ახალი შეკვეთა დაემატა!</b>\n"
           f"───────────────\n"
           f"🔢 <b>ID:</b> <code>{new_order.id}</code>\n"
               f"🏷️ <b>ნივთი:</b> {new_order.item_name}\n"
           f"📍 <b>მისამართი:</b> {new_order.city}, {new_order.address}\n"
           f"🚴 <b>კურიერი:</b> {courier.username if courier else '❌'}\n"
           f"───────────────")
    send_telegram_notification(msg)
    flash('შეკვეთა წარმატებით შეიქმნა!', 'success')
    return redirect(url_for('admin'))

@app.route('/update_order_status/<int:id>/<string:status>')
@login_required
def update_order_status(id, status):
    order_obj = db.session.get(Order, id)
    if order_obj:
        order_obj.status = status
        if status == "გზაშია":
            order_obj.courier_handed_at = datetime.utcnow()
        db.session.commit()
        flash('სტატუსი განახლდა!', 'success')
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/approve_courier/<int:id>')
@login_required
def approve_courier(id):
    if current_user.role != 'admin' and current_user.username != 'zuka abashidze': 
        return redirect(url_for('dashboard'))
    
    app_obj = db.session.get(Application, id)
    if app_obj:
        user = db.session.get(User, app_obj.user_id)
        app_obj.status = 'დადასტურებულია'
        if user:
            user.role = 'courier'
        db.session.commit()
        flash(f'კურიერი დადასტურებულია!', 'success')
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    if not os.path.exists('instance'): os.makedirs('instance')
    with app.app_context(): db.create_all()
    
    bot_thread = Thread(target=lambda: bot.polling(none_stop=True))
    bot_thread.daemon = True
    bot_thread.start()
    
    app.run(debug=True, use_reloader=False)
