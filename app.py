from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session
from werkzeug.utils import secure_filename
import os
from models import db, Video, Playlist, CustomPage, playlist_video, Admin
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from sqlalchemy import or_

app = Flask(__name__)
# Configurations
app.config['SECRET_KEY'] = 'your_secret_key_here_change_in_production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///videos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Allowed extensions
ALLOWED_EXTENSIONS = {'mp4', 'webm'}

# Initialize extensions
db.init_app(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Create database and tables
with app.app_context():
    db.create_all()
    # إنشاء حساب المسؤول الافتراضي إذا لم يكن موجوداً
    if not Admin.query.first():
        default_admin = Admin(username='admin', password=generate_password_hash('password'))
        db.session.add(default_admin)
        db.session.commit()

# دالة حماية المسارات للمسؤولين فقط
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('يجب تسجيل الدخول كمسؤول للوصول إلى هذه الصفحة.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# حقن الصفحات المخصصة وحالة تسجيل الدخول في جميع قوالب HTML
@app.context_processor
def inject_globals():
    try:
        pages = CustomPage.query.order_by(CustomPage.created_at.asc()).all()
        return dict(custom_pages=pages, is_admin=session.get('is_admin', False))
    except:
        return dict(custom_pages=[], is_admin=False)

# ---- مسارات المصادقة (Auth) ----
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password, password):
            session['is_admin'] = True
            flash('تم تسجيل الدخول بنجاح كمسؤول.', 'success')
            return redirect(url_for('index'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    flash('تم تسجيل الخروج بنجاح.', 'success')
    return redirect(url_for('index'))

@app.route('/')
def index():
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 12 # عرض 12 فيديو فقط في كل صفحة
    
    if query:
        # Search by title or tags
        videos = Video.query.filter(
            or_(
                Video.title.ilike(f'%{query}%'),
                Video.tags.ilike(f'%{query}%')
            )
        ).order_by(Video.upload_date.desc()).paginate(page=page, per_page=per_page, error_out=False)
    else:
        # All videos with pagination
        videos = Video.query.order_by(Video.upload_date.desc()).paginate(page=page, per_page=per_page, error_out=False)
        
    playlists = Playlist.query.order_by(Playlist.created_at.desc()).all()
    return render_template('index.html', videos=videos, query=query, playlists=playlists)

@app.route('/upload', methods=['GET', 'POST'])
@admin_required
def upload_video():
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'video_file' not in request.files:
            flash('لا يوجد ملف فيديو مضاف')
            return redirect(request.url)
        file = request.files['video_file']
        
        # If the user does not select a file
        if file.filename == '':
            flash('لم يتم اختيار أي ملف')
            return redirect(request.url)
            
        if file and allowed_file(file.filename):
            import uuid
            original_filename = file.filename
            extension = os.path.splitext(original_filename)[1]
            unique_filename = uuid.uuid4().hex + extension
                
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            
            default_title = os.path.splitext(original_filename)[0]
            title = request.form.get('title', '').strip()
            if not title:
                title = default_title
                
            description = request.form.get('description', '')
            tags = request.form.get('tags', '')
            
            new_video = Video(title=title, filename=unique_filename, description=description, tags=tags)
            db.session.add(new_video)
            
            # حفظ ارتباط القائمة إذا تم اختيارها
            playlist_id = request.form.get('playlist_id')
            if playlist_id:
                try:
                    playlist = Playlist.query.get(playlist_id)
                    if playlist:
                        playlist.videos.append(new_video)
                except:
                    pass
            
            db.session.commit()
            
            flash('تم رفع الفيديو بنجاح!')
            return redirect(url_for('index'))
        else:
            flash('صيغة الملف غير مدعومة.')
            return redirect(request.url)

    playlists = Playlist.query.order_by(Playlist.created_at.desc()).all()
    return render_template('upload.html', playlists=playlists)

@app.route('/edit/<int:video_id>', methods=['GET', 'POST'])
@admin_required
def edit_video(video_id):
    video = Video.query.get_or_404(video_id)
    if request.method == 'POST':
        video.title = request.form.get('title', video.title)
        video.description = request.form.get('description', '')
        video.tags = request.form.get('tags', '')
        db.session.commit()
        flash('تم تحديث بيانات الفيديو بنجاح!')
        return redirect(url_for('watch_video', video_id=video.id))
    return render_template('edit.html', video=video)

@app.route('/video/<int:video_id>')
def watch_video(video_id):
    video = Video.query.get_or_404(video_id)
    # زيادة عدد المشاهدات
    video.views += 1
    db.session.commit()
    
    playlists = Playlist.query.order_by(Playlist.created_at.desc()).all()
    return render_template('video.html', video=video, playlists=playlists)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/download/<int:video_id>')
def download_video(video_id):
    video = Video.query.get_or_404(video_id)
    
    # زيادة عدد التحميلات
    video.downloads += 1
    db.session.commit()
    
    extension = os.path.splitext(video.filename)[1]
    # التأكد من أن العنوان لا يحتوي على امتداد مسبقاً وتكوين اسم آمن للمستخدم
    safe_title = "".join(c for c in video.title if c.isalnum() or c in (' ', '-', '_')).strip()
    download_name = f"{safe_title}{extension}" if safe_title else video.filename
    return send_from_directory(app.config['UPLOAD_FOLDER'], video.filename, as_attachment=True, download_name=download_name)

@app.route('/delete/<int:video_id>', methods=['POST'])
@admin_required
def delete_video(video_id):
    video = Video.query.get_or_404(video_id)
    
    # حذف الملف الفعلي من المجلد
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], video.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        
    # حذف السجل من قاعدة البيانات
    db.session.delete(video)
    db.session.commit()
    
    flash('تم حذف الفيديو بنجاح!')
    return redirect(url_for('index'))

@app.route('/playlists', methods=['GET', 'POST'])
@admin_required
def manage_playlists():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        page_id = request.form.get('page_id')
        
        if page_id == '':
            page_id = None
            
        if name:
            new_playlist = Playlist(name=name, description=description, page_id=page_id)
            db.session.add(new_playlist)
            db.session.commit()
            flash('تم إنشاء قائمة جديدة بنجاح!')
        else:
            flash('يجب إدخال اسم القائمة.')
        return redirect(url_for('manage_playlists'))
        
    playlists = Playlist.query.order_by(Playlist.created_at.desc()).all()
    pages = CustomPage.query.all()
    return render_template('playlists.html', playlists=playlists, pages=pages)

@app.route('/playlist/<int:playlist_id>')
def view_playlist(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    page = request.args.get('page', 1, type=int)
    per_page = 12
    # نحتاج هنا لاستعلام الفيديوهات الخاصة بالقائمة مع Pagination بدلاً من قراءة playlist.videos مباشرة
    videos_paginated = Video.query.join(playlist_video).join(Playlist).filter(Playlist.id == playlist_id).order_by(Video.upload_date.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('playlist.html', playlist=playlist, videos=videos_paginated)

@app.route('/delete_playlist/<int:playlist_id>', methods=['POST'])
@admin_required
def delete_playlist(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    
    # حذف القائمة (سيتم حذف ارتباطاتها تلقائياً بسبب بنية جدول الربط)
    db.session.delete(playlist)
    db.session.commit()
    
    flash('تم حذف القائمة بنجاح!')
    return redirect(url_for('manage_playlists'))

@app.route('/edit_playlist/<int:playlist_id>', methods=['GET', 'POST'])
@admin_required
def edit_playlist(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    if request.method == 'POST':
        playlist.name = request.form.get('name')
        playlist.description = request.form.get('description', '')
        
        page_id = request.form.get('page_id')
        if page_id == '':
            playlist.page_id = None
        else:
            playlist.page_id = page_id
            
        db.session.commit()
        flash('تم تحديث بيانات القائمة بنجاح!')
        return redirect(url_for('view_playlist', playlist_id=playlist.id))
        
    pages = CustomPage.query.all()
    return render_template('edit_playlist.html', playlist=playlist, pages=pages)

@app.route('/add_to_playlist', methods=['POST'])
@admin_required
def add_to_playlist():
    video_id = request.form.get('video_id')
    playlist_id = request.form.get('playlist_id')
    
    if not video_id or not playlist_id:
        flash('حدث خطأ أثناء الإضافة.')
        return redirect(request.referrer or url_for('index'))
        
    video = Video.query.get_or_404(video_id)
    playlist = Playlist.query.get_or_404(playlist_id)
    
    if video not in playlist.videos:
        playlist.videos.append(video)
        db.session.commit()
        flash(f'تمت إضافة الفيديو لقائمة "{playlist.name}" بنجاح.')
    else:
        flash('الفيديو موجود مسبقاً في هذه القائمة.')
        
    return redirect(request.referrer or url_for('index'))

@app.route('/remove_from_playlist/<int:playlist_id>/<int:video_id>', methods=['POST'])
@admin_required
def remove_from_playlist(playlist_id, video_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    video = Video.query.get_or_404(video_id)
    
    if video in playlist.videos:
        playlist.videos.remove(video)
        db.session.commit()
        flash('تمت إزالة الفيديو من القائمة بنجاح.')
        
    return redirect(url_for('view_playlist', playlist_id=playlist.id))

# --------- مسارات إدارة المستخدمين (Admins) ---------

@app.route('/users', methods=['GET', 'POST'])
@admin_required
def manage_users():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username and password:
            existing_user = Admin.query.filter_by(username=username).first()
            if existing_user:
                flash('اسم المستخدم موجود مسبقاً. يرجى اختيار اسم آخر.', 'error')
            else:
                new_admin = Admin(username=username, password=generate_password_hash(password))
                db.session.add(new_admin)
                db.session.commit()
                flash('تم إضافة المستخدم الجديد بنجاح!', 'success')
        else:
            flash('يرجى ملء جميع الحقول.', 'error')
        return redirect(url_for('manage_users'))
        
    users = Admin.query.order_by(Admin.id.asc()).all()
    return render_template('users.html', users=users)

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = Admin.query.get_or_404(user_id)
    
    # منع حذف المشرف الأساسي (أول حساب) لتجنب فقدان إمكانية الدخول تماماً
    if user.id == 1:
        flash('لا يمكن حذف حساب المشرف الرئيسي.', 'error')
    else:
        db.session.delete(user)
        db.session.commit()
        flash('تم حذف المستخدم بنجاح.', 'success')
        
    return redirect(url_for('manage_users'))

# --------- مسارات إدارة الصفحات المخصصة (Custom Pages) ---------

@app.route('/manage_pages', methods=['GET', 'POST'])
@admin_required
def manage_pages():
    import uuid
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        if name:
            # توليد Slug عشوائي أو مبني على الاسم، لتجنب التعقيد سنستخدم uuid مبسط
            slug = str(uuid.uuid4())[:8]
            new_page = CustomPage(name=name, description=description, slug=slug)
            db.session.add(new_page)
            db.session.commit()
            flash('تم إنشاء الصفحة الجديدة بنجاح!')
        else:
            flash('يجب إدخال اسم الصفحة.')
        return redirect(url_for('manage_pages'))
        
    pages = CustomPage.query.order_by(CustomPage.created_at.desc()).all()
    return render_template('manage_pages.html', pages=pages)

@app.route('/delete_page/<int:page_id>', methods=['POST'])
@admin_required
def delete_page(page_id):
    page = CustomPage.query.get_or_404(page_id)
    db.session.delete(page)
    db.session.commit()
    flash('تم حذف الصفحة بنجاح.')
    return redirect(url_for('manage_pages'))

@app.route('/p/<slug>')
def view_page(slug):
    page_data = CustomPage.query.filter_by(slug=slug).first_or_404()
    
    # دعم تقسيم الصفحات للقوائم التابعة لهذا القسم
    page_num = request.args.get('page', 1, type=int)
    per_page = 5 # نعرض 5 قوائم لكل صفحة (لأن كل قائمة تحتوي فيديوهاتها بداخلها)
    
    playlists_paginated = Playlist.query.filter_by(page_id=page_data.id).order_by(Playlist.created_at.desc()).paginate(page=page_num, per_page=per_page, error_out=False)
    
    return render_template('lectures.html', playlists=playlists_paginated, page_title=page_data.name, page_slug=page_data.slug)

if __name__ == '__main__':
    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True, port=5100)

