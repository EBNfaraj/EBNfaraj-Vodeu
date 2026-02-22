from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    filename = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    tags = db.Column(db.String(500), nullable=True) # Tags separated by comma
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    views = db.Column(db.Integer, default=0)
    downloads = db.Column(db.Integer, default=0)

playlist_video = db.Table('playlist_video',
    db.Column('playlist_id', db.Integer, db.ForeignKey('playlist.id'), primary_key=True),
    db.Column('video_id', db.Integer, db.ForeignKey('video.id'), primary_key=True)
)

class CustomPage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # ربط الصفحة بقوائم التشغيل (One-to-Many)
    playlists = db.relationship('Playlist', backref='custom_page', lazy=True)

class Playlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    show_in_lectures = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # مفتاح أجنبي يشير للصفحة المخصصة (إذا كانت تابعة لصفحة)
    page_id = db.Column(db.Integer, db.ForeignKey('custom_page.id'), nullable=True)
    
    videos = db.relationship('Video', secondary=playlist_video, lazy='subquery',
        backref=db.backref('playlists', lazy=True))

    def __repr__(self):
        return f'<Playlist {self.name}>'

    def __repr__(self):
        return f'<Video {self.title}>'
