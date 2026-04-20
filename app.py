from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import io
import zipfile
import tempfile
import sqlite3
import math
from datetime import datetime
from datetime import date, timedelta
import json
from markupsafe import Markup
from sqlalchemy import or_, event
import re
try:
    from markdown import markdown as _md
except Exception:
    _md = None

app = Flask(__name__, instance_relative_config=True)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
# Ensure instance directory exists, then build absolute DB path
try:
    os.makedirs(app.instance_path, exist_ok=True)
except Exception:
    pass
_abs_db_path = os.path.join(app.instance_path, 'vibewrite.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + _abs_db_path.replace('\\', '/')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# Ensure essential directories exist
try:
    uploads_dir = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    os.makedirs(uploads_dir, exist_ok=True)
except Exception:
    pass

# SQLite PRAGMAs will be configured after the app context is available in __main__

# Register markdown filter for templates
@app.template_filter('markdown')
def markdown_filter(text):
    content = text or ""
    # Convert Markdown to HTML first (if available)
    html = _md(content) if _md is not None else content

    # --- EmbedPress-style auto-embeds ---
    # YouTube
    def _embed_youtube(m):
        vid = m.group(1)
        return f'<div class="ratio ratio-16x9 mb-3"><iframe src="https://www.youtube.com/embed/{vid}" title="YouTube video" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe></div>'
    html = re.sub(r"https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})\b[\w\-\?=&%]*", _embed_youtube, html)

    # Spotify
    def _embed_spotify(m):
        typ, sid = m.group(1), m.group(2)
        return f'<div class="mb-3"><iframe style="border-radius:12px" src="https://open.spotify.com/embed/{typ}/{sid}" width="100%" height="152" frameborder="0" allowfullscreen="" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"></iframe></div>'
    html = re.sub(r"https?://open\.spotify\.com/(track|album|playlist|episode|show)/([A-Za-z0-9]+)\b[\w\-\?=&%]*", _embed_spotify, html)

    # Instagram (post)
    def _embed_instagram(m):
        code = m.group(1)
        return f'<div class="mb-3"><iframe src="https://www.instagram.com/p/{code}/embed" width="100%" height="600" frameborder="0" scrolling="no" allowtransparency="true"></iframe></div>'
    html = re.sub(r"https?://www\.instagram\.com/p/([A-Za-z0-9_-]+)/?", _embed_instagram, html)

    # X/Twitter (status)
    def _embed_twitter(m):
        url = m.group(0)
        return f'<blockquote class="twitter-tweet"><a href="{url}"></a></blockquote>'
    html = re.sub(r"https?://twitter\.com/[^/]+/status/\d+\b[\w\-\?=&%]*", _embed_twitter, html)
    html = re.sub(r"https?://x\.com/[^/]+/status/\d+\b[\w\-\?=&%]*", _embed_twitter, html)

    # --- Lightbox Gallery: wrap images in anchors for GLightbox ---
    def _wrap_img(m):
        tag = m.group(0)
        # Extract src
        src_m = re.search(r'src=\"([^\"]+)\"', tag)
        if not src_m:
            return tag
        src = src_m.group(1)
        return f'<a href="{src}" class="glightbox" data-gallery="post-gallery">{tag}</a>'
    html = re.sub(r"<img\b[^>]*>", _wrap_img, html)

    return Markup(html)

# ===== MODELS =====
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), nullable=False, default='reader')
    profile_picture = db.Column(db.String(200), default='default.jpg')
    bio = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    points = db.Column(db.Integer, default=0)
    badges = db.Column(db.Text, default='[]')
    
    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='user', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)
    ads = db.relationship('Ad', backref='advertiser', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def add_badge(self, badge_name):
        badges = json.loads(self.badges)
        if badge_name not in badges:
            badges.append(badge_name)
            self.badges = json.dumps(badges)
    
    def get_badges(self):
        return json.loads(self.badges)

    def has_liked(self, post):
        """Return True if this user has liked the given post."""
        if not post or not hasattr(post, 'id'):
            return False
        return Like.query.filter_by(user_id=self.id, post_id=post.id).first() is not None

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    excerpt = db.Column(db.Text)
    featured_image = db.Column(db.String(200))
    visibility = db.Column(db.String(20), default='public')
    password = db.Column(db.String(100))
    tags = db.Column(db.Text)
    category = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_published = db.Column(db.Boolean, default=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    featured_ad_id = db.Column(db.Integer, db.ForeignKey('ad.id'))

    # Relationships
    comments = db.relationship('Comment', backref='post', lazy=True)
    likes = db.relationship('Like', backref='post', lazy=True)
    featured_ad = db.relationship('Ad', foreign_keys=[featured_ad_id])

    # Helpers used in templates
    def like_count(self):
        return Like.query.filter_by(post_id=self.id).count()
    
    def comment_count(self):
        return Comment.query.filter_by(post_id=self.id).count()

    def reading_time(self):
        """Estimate reading time in minutes (200 wpm). Minimum 1 minute."""
        if not self.content:
            return 1
        words = len(self.content.split())
        return max(1, math.ceil(words / 200))

    @property
    def author_id(self):
        """Compatibility alias for templates expecting author_id."""
        return self.user_id

    @property
    def views(self):
        """Count unique PostView records for this post."""
        return PostView.query.filter_by(post_id=self.id).count()

class PostView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='uq_postview_user_post'),)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_approved = db.Column(db.Boolean, default=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class UserProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    reader_streak = db.Column(db.Integer, default=0)
    last_read_date = db.Column(db.Date)
    daily_login_date = db.Column(db.Date)
    streak_freeze_tokens = db.Column(db.Integer, default=0)
    writer_xp = db.Column(db.Integer, default=0)
    writer_tier = db.Column(db.String(20), default='Bronze')

def _get_progress(user):
    p = UserProgress.query.filter_by(user_id=user.id).first()
    if not p:
        p = UserProgress(user_id=user.id)
        db.session.add(p)
        db.session.commit()
    return p

_LEVELS = [0, 100, 250, 500, 900, 1400, 2000]

def _recalc_level(xp: int) -> int:
    lvl = 1
    for i, th in enumerate(_LEVELS, start=1):
        if xp >= th:
            lvl = i
    return lvl

def add_reader_xp(user, amount):
    try:
        p = _get_progress(user)
        p.xp = max(0, (p.xp or 0) + int(amount))
        p.level = _recalc_level(p.xp)
        db.session.commit()
    except Exception:
        db.session.rollback()

def add_writer_xp(user, amount):
    try:
        p = _get_progress(user)
        p.writer_xp = max(0, (p.writer_xp or 0) + int(amount))
        # Simple tiering
        if p.writer_xp >= 600:
            p.writer_tier = 'Gold'
        elif p.writer_xp >= 200:
            p.writer_tier = 'Silver'
        else:
            p.writer_tier = 'Bronze'
        db.session.commit()
    except Exception:
        db.session.rollback()

def update_reading_streak(user):
    try:
        today = date.today()
        p = _get_progress(user)
        if p.last_read_date is None:
            prev = 0
            p.reader_streak = 1
        else:
            if p.last_read_date == today:
                # already counted today
                return
            if p.last_read_date == today - timedelta(days=1):
                prev = (p.reader_streak or 0)
                p.reader_streak = prev + 1
            else:
                # one-day grace with freeze token
                if p.last_read_date == today - timedelta(days=2) and (p.streak_freeze_tokens or 0) > 0:
                    p.streak_freeze_tokens -= 1
                    prev = (p.reader_streak or 0)
                    p.reader_streak = prev + 1
                else:
                    prev = 0
                    p.reader_streak = 1
        p.last_read_date = today
        # Award a freeze token at each 7-day milestone (7,14,21,...)
        try:
            if p.reader_streak % 7 == 0 and (prev % 7 != 0):
                p.streak_freeze_tokens = (p.streak_freeze_tokens or 0) + 1
        except Exception:
            pass
        db.session.commit()
    except Exception:
        db.session.rollback()

def award_daily_login_xp(user):
    try:
        today = date.today()
        p = _get_progress(user)
        if p.daily_login_date != today:
            p.daily_login_date = today
            p.xp = (p.xp or 0) + 2
            p.level = _recalc_level(p.xp)
            db.session.commit()
    except Exception:
        db.session.rollback()

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Ad(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    image_url = db.Column(db.String(200))
    target_url = db.Column(db.String(200))
    ad_type = db.Column(db.String(50))
    status = db.Column(db.String(20), default='pending')
    clicks = db.Column(db.Integer, default=0)
    impressions = db.Column(db.Integer, default=0)
    budget = db.Column(db.Float, default=0.0)
    featured_home = db.Column(db.Boolean, default=False)
    cpi = db.Column(db.Float, default=0.01)  # cost per impression on feed
    cpi_home = db.Column(db.Float, default=0.05)  # extra for home page
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def ctr(self):
        """Return click-through rate percentage as float rounded to 2 decimals."""
        return round((self.clicks / self.impressions * 100), 2) if self.impressions and self.impressions > 0 else 0.0

    @property
    def spent(self):
        """Amount spent so far. Not tracked yet, so default to 0.0 to satisfy templates."""
        return 0.0

class Backup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(300), nullable=False)
    backup_type = db.Column(db.String(50))
    file_size = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
# ===== MODELS =====
# ... your existing models ...

# ===== BADGE HELPERS =====
def award_point_milestones(user):
    try:
        if user.points >= 100:
            user.add_badge('100 Points')
        if user.points >= 250:
            user.add_badge('250 Points')
        if user.points >= 500:
            user.add_badge('500 Points')
    except Exception:
        pass

def award_post_milestones(author):
    try:
        post_count = Post.query.filter_by(user_id=author.id).count()
        if post_count >= 1:
            author.add_badge('First Post')
        if post_count >= 5:
            author.add_badge('5 Posts')
        if post_count >= 10:
            author.add_badge('10 Posts')
    except Exception:
        pass

def award_comment_milestones(user):
    try:
        comment_count = Comment.query.filter_by(user_id=user.id).count()
        if comment_count >= 1:
            user.add_badge('First Comment')
        if comment_count >= 10:
            user.add_badge('10 Comments')
    except Exception:
        pass

def award_likes_given_milestones(user):
    try:
        likes_given = Like.query.filter_by(user_id=user.id).count()
        if likes_given >= 1:
            user.add_badge('First Like')
        if likes_given >= 50:
            user.add_badge('50 Likes Given')
    except Exception:
        pass

def award_engagement_milestones(post):
    try:
        # Award to the author based on engagement of this post
        author = User.query.get(post.user_id)
        if not author:
            return
        like_count = Like.query.filter_by(post_id=post.id).count()
        comment_count = Comment.query.filter_by(post_id=post.id).count()
        if like_count >= 10:
            author.add_badge('Post 10 Likes')
        if like_count >= 50:
            author.add_badge('Post 50 Likes')
        if comment_count >= 10:
            author.add_badge('Post 10 Comments')
        if comment_count >= 50:
            author.add_badge('Post 50 Comments')
    except Exception:
        pass

# ===== FORMS =====
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', 
                                   validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', choices=[
        ('reader', 'Reader'),
        ('author', 'Author'),
        ('advertiser', 'Advertiser')
    ], validators=[DataRequired()])
    submit = SubmitField('Register')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is already taken.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is already registered.')

class PostForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    content = TextAreaField('Content', validators=[DataRequired()])
    excerpt = TextAreaField('Excerpt')
    featured_image = FileField('Featured Image', 
                              validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'])])
    visibility = SelectField('Visibility', choices=[
        ('public', 'Public'),
        ('private', 'Private'),
        ('password', 'Password Protected')
    ])
    password = PasswordField('Post Password')
    tags = StringField('Tags (comma separated)')
    category = StringField('Category')
    submit = SubmitField('Publish Post')

class CommentForm(FlaskForm):
    content = TextAreaField('Comment', validators=[DataRequired(), Length(max=1000)])
    submit = SubmitField('Post Comment')

class AdForm(FlaskForm):
    title = StringField('Ad Title', validators=[DataRequired(), Length(max=200)])
    content = TextAreaField('Ad Content')
    image_url = StringField('Image URL')
    target_url = StringField('Target URL', validators=[DataRequired()])
    ad_type = SelectField('Ad Type', choices=[
        ('banner', 'Banner'),
        ('sidebar', 'Sidebar'),
        ('inline', 'Inline')
    ], validators=[DataRequired()])
    budget = StringField('Budget')
    start_date = StringField('Start Date')
    end_date = StringField('End Date')
    submit = SubmitField('Create Ad')

class BackupForm(FlaskForm):
    backup_type = SelectField('Backup Type', choices=[
        ('full', 'Full Backup'),
        ('posts', 'Posts Only'),
        ('users', 'Users Only')
    ])
    submit = SubmitField('Create Backup')

# ===== ROUTES =====
# ... your existing routes ...

# Main Routes
@app.route('/')
def index():
    posts = Post.query.filter_by(visibility='public', is_published=True).order_by(Post.created_at.desc()).limit(6).all()
    # Featured home ads (charge extra per impression)
    home_ads = Ad.query.filter_by(status='active', featured_home=True).order_by(Ad.created_at.desc()).limit(3).all()
    # Charge impressions
    try:
        changed = False
        for ad in home_ads:
            cost = ad.cpi_home or 0.0
            if ad.budget is None or ad.budget >= cost:
                ad.impressions = (ad.impressions or 0) + 1
                if ad.budget is not None:
                    ad.budget = max(0.0, float(ad.budget) - float(cost))
                changed = True
        if changed:
            db.session.commit()
    except Exception:
        db.session.rollback()
    return render_template('index.html', posts=posts, home_ads=home_ads)

@app.route('/search')
def search():
    q = (request.args.get('q') or '').strip()
    page = request.args.get('page', type=int, default=1)
    base = Post.query.filter_by(visibility='public', is_published=True)
    if q:
        like = f"%{q}%"
        base = base.join(User, Post.user_id == User.id).filter(
            or_(
                Post.title.ilike(like),
                Post.content.ilike(like),
                Post.tags.ilike(like),
                User.username.ilike(like)
            )
        )
    base = base.order_by(Post.created_at.desc())
    posts = db.paginate(base, page=page, per_page=10, error_out=False)
    return render_template('reader/search.html', posts=posts, query=q)

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        total_users = User.query.count()
        total_posts = Post.query.count()
        total_ads = Ad.query.count()
        pending_ads = Ad.query.filter_by(status='pending').count()
        # Last backup timestamp
        last_b = Backup.query.filter_by(backup_type='full').order_by(Backup.created_at.desc()).first()
        last_backup_at = last_b.created_at if last_b else None
        return render_template('admin/dashboard.html', 
                             total_users=total_users, total_posts=total_posts,
                             total_ads=total_ads, pending_ads=pending_ads,
                             last_backup_at=last_backup_at)
    elif current_user.role == 'author':
        posts = Post.query.filter_by(user_id=current_user.id).all()
        total_likes = sum(post.like_count() for post in posts)
        total_comments = sum(post.comment_count() for post in posts)
        # Audience achievements
        # Total reads across author's posts
        from sqlalchemy import func
        total_reads = db.session.query(func.count(PostView.id))\
            .join(Post, PostView.post_id == Post.id)\
            .filter(Post.user_id == current_user.id).scalar() or 0
        # Returning readers: users who viewed on 2+ distinct days
        returning_readers = db.session.query(PostView.user_id, func.count(func.distinct(func.date(PostView.created_at))))\
            .join(Post, PostView.post_id == Post.id)\
            .filter(Post.user_id == current_user.id)\
            .group_by(PostView.user_id)\
            .having(func.count(func.distinct(func.date(PostView.created_at))) >= 2).count()
        prog = _get_progress(current_user)
        return render_template('author/dashboard.html', 
                             posts=posts, total_likes=total_likes,
                             total_comments=total_comments,
                             total_reads=total_reads,
                             returning_readers=returning_readers,
                             writer_tier=prog.writer_tier,
                             writer_xp=prog.writer_xp)
    elif current_user.role == 'advertiser':
        ads = Ad.query.filter_by(user_id=current_user.id).all()
        total_clicks = sum(ad.clicks for ad in ads)
        total_impressions = sum(ad.impressions for ad in ads)
        ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        return render_template('advertiser/dashboard.html',
                             ads=ads, total_clicks=total_clicks, 
                             total_impressions=total_impressions, ctr=round(ctr, 2))
    else:
        posts = Post.query.filter_by(visibility='public', is_published=True).order_by(Post.created_at.desc()).limit(10).all()
        likes_given = Like.query.filter_by(user_id=current_user.id).count()
        comments_count = Comment.query.filter_by(user_id=current_user.id).count()
        posts_read = PostView.query.filter_by(user_id=current_user.id).count()
        # Daily login XP
        award_daily_login_xp(current_user)
        prog = _get_progress(current_user)
        return render_template('reader/dashboard.html', posts=posts,
                               likes_given=likes_given,
                               comments_count=comments_count,
                               posts_read=posts_read,
                               xp=prog.xp, level=prog.level, reader_streak=prog.reader_streak)

# ===== Advertiser Ads Management =====
@app.route('/advertiser/ads')
@login_required
def advertiser_ads():
    if current_user.role != 'advertiser':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    ads = Ad.query.filter_by(user_id=current_user.id).order_by(Ad.created_at.desc()).all()
    return render_template('advertiser/ads_list.html', ads=ads)

@app.route('/advertiser/ads/new', methods=['GET', 'POST'])
@login_required
def advertiser_new_ad():
    if current_user.role != 'advertiser':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        title = request.form.get('title')
        target_url = request.form.get('target_url')
        if not title or not target_url:
            flash('Title and Target URL are required.', 'danger')
            return redirect(request.url)
        content = request.form.get('content')
        image_url = request.form.get('image_url')
        ad_type = request.form.get('ad_type') or 'inline'
        budget = request.form.get('budget') or '0'
        cpi = request.form.get('cpi') or '0.01'
        featured_home = True if request.form.get('featured_home') == 'on' else False
        cpi_home = request.form.get('cpi_home') or '0.05'
        try:
            ad = Ad(
                title=title,
                content=content,
                image_url=image_url,
                target_url=target_url,
                ad_type=ad_type,
                status='pending',
                budget=float(budget) if budget is not None and budget != '' else 0.0,
                cpi=float(cpi) if cpi is not None and cpi != '' else 0.01,
                featured_home=featured_home,
                cpi_home=float(cpi_home) if cpi_home is not None and cpi_home != '' else 0.05,
                user_id=current_user.id
            )
            db.session.add(ad)
            db.session.commit()
            flash('Ad created successfully.', 'success')
            return redirect(url_for('advertiser_ads'))
        except Exception:
            db.session.rollback()
            flash('Failed to create ad. Please try again.', 'danger')
    return render_template('advertiser/ad_form.html', ad=None)

@app.route('/advertiser/ads/<int:ad_id>/edit', methods=['GET', 'POST'])
@login_required
def advertiser_edit_ad(ad_id):
    if current_user.role != 'advertiser':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    ad = Ad.query.filter_by(id=ad_id, user_id=current_user.id).first_or_404()
    if request.method == 'POST':
        ad.title = request.form.get('title')
        ad.content = request.form.get('content')
        ad.image_url = request.form.get('image_url')
        ad.target_url = request.form.get('target_url')
        ad.ad_type = request.form.get('ad_type') or ad.ad_type
        budget = request.form.get('budget')
        cpi = request.form.get('cpi')
        cpi_home = request.form.get('cpi_home')
        ad.featured_home = True if request.form.get('featured_home') == 'on' else False
        try:
            if budget is not None and budget != '':
                ad.budget = float(budget)
            if cpi is not None and cpi != '':
                ad.cpi = float(cpi)
            if cpi_home is not None and cpi_home != '':
                ad.cpi_home = float(cpi_home)
            db.session.commit()
            flash('Ad updated successfully.', 'success')
            return redirect(url_for('advertiser_ads'))
        except Exception:
            db.session.rollback()
            flash('Failed to update ad. Please try again.', 'danger')
    return render_template('advertiser/ad_form.html', ad=ad)

@app.route('/leaderboards')
def leaderboards():
    # timeframe: daily/weekly/monthly
    tf = request.args.get('t', 'daily')
    tag = request.args.get('tag')
    now = datetime.utcnow()
    if tf == 'weekly':
        start = now - timedelta(days=7)
    elif tf == 'monthly':
        start = now - timedelta(days=30)
    else:
        start = now - timedelta(days=1)
    # Base query: reader activity by reads
    from sqlalchemy import func
    q = db.session.query(PostView.user_id, func.count(PostView.id).label('score'))\
        .filter(PostView.created_at >= start)
    if tag:
        q = q.join(Post, Post.id == PostView.post_id).filter(Post.tags.ilike(f"%{tag}%"))
    q = q.group_by(PostView.user_id).order_by(db.desc('score')).limit(20)
    rows = q.all()
    user_ids = [uid for uid, _ in rows]
    users = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()}
    leaderboard = [{'user': users.get(uid), 'score': score} for uid, score in rows]
    return render_template('reader/leaderboards.html', leaderboard=leaderboard, timeframe=tf, tag=tag)

# ===== Admin Backups =====
@app.route('/admin/backups', methods=['GET', 'POST'])
@login_required
def admin_backups():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        # Create full-site backup (DB + uploads)
        try:
            backups_dir = os.path.join(app.root_path, 'backups', 'site')
            os.makedirs(backups_dir, exist_ok=True)
            ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f'backup_full_{ts}.zip'
            zip_path = os.path.join(backups_dir, filename)
            with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                # Add consistent database snapshot via SQLite online backup
                db_uri = app.config['SQLALCHEMY_DATABASE_URI']
                db_file = 'vibewrite.db'
                if db_uri.startswith('sqlite:///'):
                    db_file = db_uri.replace('sqlite:///', '')
                db_abs = db_file if os.path.isabs(db_file) else os.path.join(app.root_path, db_file)
                if os.path.exists(db_abs):
                    tmp_sqlite = os.path.join(backups_dir, f"db_snapshot_{ts}.sqlite")
                    try:
                        with sqlite3.connect(db_abs) as src_conn:
                            with sqlite3.connect(tmp_sqlite) as dst_conn:
                                src_conn.backup(dst_conn)
                        zf.write(tmp_sqlite, arcname='vibewrite.db')
                    finally:
                        try:
                            if os.path.exists(tmp_sqlite):
                                os.remove(tmp_sqlite)
                        except Exception:
                            pass
                # Add uploads directory
                uploads_dir = os.path.join(app.root_path, app.config.get('UPLOAD_FOLDER', 'static/uploads'))
                if os.path.isdir(uploads_dir):
                    for root, _, files in os.walk(uploads_dir):
                        for f in files:
                            full = os.path.join(root, f)
                            rel = os.path.relpath(full, app.root_path)
                            zf.write(full, arcname=rel)
            # Record backup entry
            try:
                size_bytes = os.path.getsize(zip_path)
                size_mb = f"{size_bytes/1024/1024:.2f} MB"
            except Exception:
                size_mb = 'n/a'
            b = Backup(filename=filename, file_path=zip_path, backup_type='full', file_size=size_mb)
            db.session.add(b)
            db.session.commit()
            flash('Backup created successfully.', 'success')
        except Exception:
            db.session.rollback()
            flash('Failed to create backup.', 'danger')
        return redirect(url_for('admin_backups'))
    backups = Backup.query.filter_by(backup_type='full').order_by(Backup.created_at.desc()).all()
    return render_template('admin/backups.html', backups=backups)

@app.route('/admin/backups/<int:backup_id>/download')
@login_required
def admin_backup_download(backup_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    b = Backup.query.get_or_404(backup_id)
    if not os.path.exists(b.file_path):
        flash('Backup file not found.', 'danger')
        return redirect(url_for('admin_backups'))
    return send_file(b.file_path, as_attachment=True, download_name=b.filename)

# Auth Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.is_active:
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        flash('Invalid email or password', 'danger')
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'reader')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
        elif User.query.filter_by(username=username).first():
            flash('Username already taken', 'danger')
        else:
            user = User(username=username, email=email, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Account created successfully! You can now log in.', 'success')
            return redirect(url_for('login'))
    return render_template('auth/register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# Author Routes
@app.route('/author/my-posts')
@login_required
def my_posts():
    if current_user.role != 'author':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    posts = Post.query.filter_by(user_id=current_user.id).order_by(Post.created_at.desc()).all()
    return render_template('author/my_posts.html', posts=posts)

@app.route('/author/posts')
@login_required
def author_posts():
    if current_user.role != 'author':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    posts = Post.query.filter_by(user_id=current_user.id).order_by(Post.created_at.desc()).all()
    return render_template('author/my_posts.html', posts=posts)

@app.route('/author/create-post', methods=['GET', 'POST'])
@login_required
def create_post():
    if current_user.role != 'author':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        excerpt = request.form.get('excerpt')
        category = request.form.get('category')
        visibility = request.form.get('visibility', 'public')
        password = request.form.get('password') if visibility == 'password' else None
        tags = request.form.get('tags')
        featured_ad_id = request.form.get('featured_ad_id', type=int)
        
        post = Post(title=title, content=content, excerpt=excerpt, category=category,
                    visibility=visibility, password=password, tags=tags,
                    user_id=current_user.id, featured_ad_id=featured_ad_id)
        
        if 'featured_image' in request.files:
            file = request.files['featured_image']
            if file and file.filename:
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                post.featured_image = filename
        
        db.session.add(post)
        current_user.points += 10
        db.session.commit()

        # Award badges after persistence
        award_post_milestones(current_user)
        award_point_milestones(current_user)
        award_engagement_milestones(post)
        db.session.commit()

        flash('Post created successfully!', 'success')
        return redirect(url_for('author_posts'))
    # Active ads available to feature under posts
    active_ads = Ad.query.filter_by(status='active').order_by(Ad.created_at.desc()).all()
    return render_template('author/create_post.html', active_ads=active_ads)

@app.route('/author/edit-post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.filter_by(id=post_id, user_id=current_user.id).first_or_404()
    if request.method == 'POST':
        post.title = request.form.get('title')
        post.content = request.form.get('content')
        post.excerpt = request.form.get('excerpt')
        post.category = request.form.get('category')
        post.visibility = request.form.get('visibility', 'public')
        post.password = request.form.get('password') if post.visibility == 'password' else None
        post.tags = request.form.get('tags')
        post.featured_ad_id = request.form.get('featured_ad_id', type=int)
        # Handle featured image upload if provided
        if 'featured_image' in request.files:
            file = request.files['featured_image']
            if file and file.filename:
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                post.featured_image = filename
        db.session.commit()
        flash('Post updated successfully!', 'success')
        return redirect(url_for('author_posts'))
    active_ads = Ad.query.filter_by(status='active').order_by(Ad.created_at.desc()).all()
    return render_template('author/edit_post.html', post=post, active_ads=active_ads)

@app.route('/author/delete-post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.filter_by(id=post_id, user_id=current_user.id).first_or_404()
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted successfully!', 'success')
    return redirect(url_for('my_posts'))

@app.route('/author/export', methods=['GET'])
@login_required
def author_export():
    if current_user.role != 'author':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    posts = Post.query.filter_by(user_id=current_user.id).order_by(Post.created_at.desc()).all()
    # Create a temporary zip file
    tmp_dir = tempfile.mkdtemp(prefix='vibewrite_export_')
    zip_path = os.path.join(tmp_dir, f"vibewrite_export_user_{current_user.id}.zip")
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        # index.html listing
        index_html = [
            '<!doctype html>','<html><head><meta charset="utf-8"><title>My VibeWrite Export</title>',
            '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">',
            '</head><body class="p-4">',
            '<h1 class="h3 mb-4">My VibeWrite Export</h1>',
            '<p class="text-muted">This archive contains rendered HTML versions of your posts as displayed on the site, and your uploaded media under <code>static/uploads/</code>.</p>',
            '<ul class="list-group">'
        ]
        for post in posts:
            fname = f"post_{post.id}.html"
            date_str = post.created_at.strftime("%Y-%m-%d") if post.created_at else ""
            index_html.append(f"<li class=\"list-group-item\"><a href=\"{fname}\">{post.title}</a> <small class=\"text-muted\">({date_str})</small></li>")
            # Render content using the same markdown filter
            rendered = str(markdown_filter(post.content)) if post.content else ''
            img_html = f"<div class=\"mt-3\"><img class=\"img-fluid rounded\" src=\"static/uploads/{post.featured_image}\" alt=\"Featured\"></div>" if getattr(post, 'featured_image', None) else ''
            tags_html = f"<div class=\"mt-3\">Tags: {post.tags}</div>" if getattr(post, 'tags', None) else ''
            pretty_date = post.created_at.strftime("%B %d, %Y") if post.created_at else ""
            post_html = f"""
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\">
  <title>{post.title}</title>
  <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css\">
</head>
<body class=\"container py-4\">
  <h1 class=\"h3 fw-bold mb-2\">{post.title}</h1>
  <div class=\"text-muted mb-3\">{pretty_date}</div>
  {rendered}
  {img_html}
  {tags_html}
  <hr>
  <p class=\"text-muted\">Exported from VibeWrite</p>
  <script src=\"https://platform.twitter.com/widgets.js\" async></script>
  <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/glightbox/dist/css/glightbox.min.css\"> 
  <script src=\"https://cdn.jsdelivr.net/npm/glightbox/dist/js/glightbox.min.js\"></script>
  <script> if (typeof GLightbox!== 'undefined') GLightbox(); </script>
</body>
</html>
"""
            zf.writestr(fname, post_html)
        index_html.append('</ul></body></html>')
        zf.writestr('index.html', '\n'.join(index_html))
        # Include uploaded media directory under static/uploads
        uploads_dir = os.path.join(app.root_path, app.config.get('UPLOAD_FOLDER', 'static/uploads'))
        if os.path.isdir(uploads_dir):
            for root, _, files in os.walk(uploads_dir):
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, app.root_path)  # e.g., static/uploads/...
                    zf.write(full, rel)
    # Send the zip file to the user
    return send_file(zip_path, as_attachment=True, download_name=f"vibewrite_export_{current_user.username}.zip")

# Reader Routes
@app.route('/feed')
@login_required
def feed():
    posts = Post.query.filter_by(visibility='public', is_published=True).order_by(Post.created_at.desc()).all()
    # Active ads for interleaving
    ads = Ad.query.filter_by(status='active').order_by(Ad.created_at.desc()).all()
    # Determine how many ads to show (e.g., 1 per 3 posts)
    slots = max(1, len(posts) // 3) if posts else 0
    display_ads = ads[:slots]
    # Charge impressions on displayed ads
    try:
        changed = False
        for ad in display_ads:
            cost = ad.cpi or 0.0
            if ad.budget is None or ad.budget >= cost:
                ad.impressions = (ad.impressions or 0) + 1
                if ad.budget is not None:
                    ad.budget = max(0.0, float(ad.budget) - float(cost))
                changed = True
        if changed:
            db.session.commit()
    except Exception:
        db.session.rollback()
    return render_template('reader/feed.html', posts=posts, ads=display_ads)

@app.route('/post/<int:post_id>')
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    if post.visibility == 'private' and (not current_user.is_authenticated or current_user.id != post.user_id):
        flash('This post is private.', 'warning')
        return redirect(url_for('feed'))
    elif post.visibility == 'password':
        password = request.args.get('password')
        if not password or password != post.password:
            return render_template('reader/password_prompt.html', post=post)
    
    # Record view for authenticated users (unique per user/post)
    if current_user.is_authenticated:
        try:
            if not PostView.query.filter_by(user_id=current_user.id, post_id=post.id).first():
                db.session.add(PostView(user_id=current_user.id, post_id=post.id))
                db.session.commit()
                # Award read XP and update streak for readers
                if current_user.role == 'reader':
                    add_reader_xp(current_user, 5)
                    update_reading_streak(current_user)
        except Exception:
            db.session.rollback()
    return render_template('reader/view_post.html', post=post)

@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    content = request.form.get('content')
    
    if content:
        comment = Comment(content=content, user_id=current_user.id, post_id=post.id)
        db.session.add(comment)
        current_user.points += 5
        db.session.commit()

        # Award badges for commenter and engagement for author
        award_comment_milestones(current_user)
        award_point_milestones(current_user)
        award_engagement_milestones(post)
        db.session.commit()

        flash('Comment added successfully!', 'success')
    
    return redirect(url_for('view_post', post_id=post.id))

@app.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    existing_like = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first()
    
    if existing_like:
        db.session.delete(existing_like)
        db.session.commit()
    else:
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        db.session.commit()
        # Award reader XP for liking
        if current_user.role == 'reader':
            add_reader_xp(current_user, 2)
        current_user.points += 2
        liked = True
    
    db.session.commit()

    # Award badges for liker and engagement for author
    award_likes_given_milestones(current_user)
    award_point_milestones(current_user)
    award_engagement_milestones(post)
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'liked': liked, 'like_count': post.like_count()})
    
    return redirect(request.referrer or url_for('view_post', post_id=post.id))

# Comment delete route used in reader/view_post.html
@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if current_user.id != comment.user_id and current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(request.referrer or url_for('feed'))
    post_id = comment.post_id
    db.session.delete(comment)
    db.session.commit()
    flash('Comment deleted.', 'success')
    return redirect(url_for('view_post', post_id=post_id))

# Admin Routes
@app.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/user/<int:user_id>/toggle')
@login_required
def toggle_user(user_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    flash(f'User {user.username} has been {"activated" if user.is_active else "deactivated"}', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/ads')
@login_required
def admin_ads():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    ads = Ad.query.all()
    return render_template('admin/ads.html', ads=ads)

@app.route('/admin/seed-demo')
@login_required
def seed_demo():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    def get_or_create_user(username, email, password, role):
        u = User.query.filter_by(email=email).first()
        if not u:
            u = User(username=username, email=email, role=role)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
        return u

    writer1 = get_or_create_user('writer1', 'writer1@demo.com', 'demo123', 'author')
    writer2 = get_or_create_user('writer2', 'writer2@demo.com', 'demo123', 'author')
    reader1 = get_or_create_user('reader1', 'reader1@demo.com', 'demo123', 'reader')
    reader2 = get_or_create_user('reader2', 'reader2@demo.com', 'demo123', 'reader')

    def ensure_posts_for(writer, titles):
        created_posts = []
        for t in titles:
            p = Post.query.filter_by(title=t, user_id=writer.id).first()
            if not p:
                p = Post(title=t, content=f"# {t}\n\nThis is a demo post written in Markdown.\n\n- Point 1\n- Point 2\n\nEnjoy reading!", excerpt="Demo post excerpt.", visibility='public', tags='demo, sample', category='General', user_id=writer.id)
                db.session.add(p)
                writer.points += 10
                db.session.commit()
            created_posts.append(p)
        return created_posts

    posts_w1 = ensure_posts_for(writer1, [
        'Getting Started with VibeWrite',
        'Creativity Hacks for Busy Writers',
        'Top 5 Tools for Bloggers'
    ])
    posts_w2 = ensure_posts_for(writer2, [
        'Storytelling Basics',
        'How to Find Your Writing Voice',
        'Editing Like a Pro'
    ])

    def like_post_if_needed(user, post):
        if not Like.query.filter_by(user_id=user.id, post_id=post.id).first():
            l = Like(user_id=user.id, post_id=post.id)
            db.session.add(l)
            user.points += 2
            db.session.commit()

    def comment_post_if_needed(user, post, content):
        existing = Comment.query.filter_by(user_id=user.id, post_id=post.id).first()
        if not existing:
            c = Comment(content=content, user_id=user.id, post_id=post.id)
            db.session.add(c)
            user.points += 5
            db.session.commit()

    for p in posts_w1 + posts_w2:
        like_post_if_needed(reader1, p)
        like_post_if_needed(reader2, p)
        comment_post_if_needed(reader1, p, "Great insights! Thanks for sharing.")
        comment_post_if_needed(reader2, p, "Loved this post. Looking forward to more.")

    award_post_milestones(writer1)
    award_post_milestones(writer2)
    award_point_milestones(writer1)
    award_point_milestones(writer2)
    award_comment_milestones(reader1)
    award_comment_milestones(reader2)
    award_likes_given_milestones(reader1)
    award_likes_given_milestones(reader2)
    db.session.commit()

    from flask import render_template_string
    return render_template_string(
        """
        {% extends 'base.html' %}
        {% block title %}Demo Data Seeded{% endblock %}
        {% block content %}
        <section class="py-6"><div class="container">
        <div class="card"><div class="card-body">
        <h3 class="fw-bold mb-3">Demo data created</h3>
        <p>Use these accounts to log in:</p>
        <ul>
            <li><strong>Admin</strong>: admin@vibewrite.com / admin123</li>
            <li><strong>Writer 1</strong>: writer1@demo.com / demo123</li>
            <li><strong>Writer 2</strong>: writer2@demo.com / demo123</li>
            <li><strong>Reader 1</strong>: reader1@demo.com / demo123</li>
            <li><strong>Reader 2</strong>: reader2@demo.com / demo123</li>
        </ul>
        <p>Created posts for writers, with likes and comments from readers. You can now browse the feed and dashboards.</p>
        <a href="{{ url_for('feed') }}" class="btn btn-primary">Go to Feed</a>
        </div></div>
        </div></section>
        {% endblock %}
        """
    )

@app.route('/admin/ad/<int:ad_id>/<action>')
@login_required
def manage_ad(ad_id, action):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    ad = Ad.query.get_or_404(ad_id)
    
    if action == 'approve':
        ad.status = 'active'
        flash('Ad approved successfully!', 'success')
    elif action == 'reject':
        ad.status = 'rejected'
        flash('Ad rejected.', 'warning')
    elif action == 'pause':
        ad.status = 'paused'
        flash('Ad paused.', 'info')
    
    db.session.commit()
    return redirect(url_for('admin_ads'))

# (legacy advertiser routes removed in favor of unified ads management)

if __name__ == '__main__':
    # Ensure logo asset is available under static for serving
    try:
        static_img_dir = os.path.join(app.root_path, 'static', 'img')
        os.makedirs(static_img_dir, exist_ok=True)
        src_logo = os.path.join(app.root_path, 'vibewrite.png')
        dst_logo = os.path.join(static_img_dir, 'logo.png')
        if os.path.exists(src_logo):
            # Always overwrite to ensure the latest upload is served
            import shutil as _sh
            _sh.copyfile(src_logo, dst_logo)
    except Exception:
        pass

    with app.app_context():
        # Configure SQLite PRAGMAs now that engine is available
        try:
            @event.listens_for(db.engine, "connect")
            def _set_sqlite_pragmas(dbapi_connection, connection_record):
                try:
                    cur = dbapi_connection.cursor()
                    cur.execute("PRAGMA foreign_keys=ON;")
                    cur.execute("PRAGMA journal_mode=WAL;")
                    cur.close()
                except Exception:
                    pass
        except Exception:
            pass
        db.create_all()
        # Lightweight SQLite migration for newly added columns
        try:
            from sqlalchemy import text
            def column_exists(table: str, column: str) -> bool:
                rows = db.session.execute(text(f"PRAGMA table_info({table})"))
                return any(r[1] == column for r in rows)

            # post.featured_ad_id
            if not column_exists('post', 'featured_ad_id'):
                db.session.execute(text('ALTER TABLE post ADD COLUMN featured_ad_id INTEGER'))
            # ad.featured_home
            if not column_exists('ad', 'featured_home'):
                db.session.execute(text('ALTER TABLE ad ADD COLUMN featured_home BOOLEAN DEFAULT 0'))
            # ad.cpi
            if not column_exists('ad', 'cpi'):
                db.session.execute(text('ALTER TABLE ad ADD COLUMN cpi FLOAT DEFAULT 0.01'))
            # ad.cpi_home
            if not column_exists('ad', 'cpi_home'):
                db.session.execute(text('ALTER TABLE ad ADD COLUMN cpi_home FLOAT DEFAULT 0.05'))
            db.session.commit()
        except Exception:
            db.session.rollback()
        # Create admin user if doesn't exist
        if not User.query.filter_by(email='admin@vibewrite.com').first():
            admin = User(username='admin', email='admin@vibewrite.com', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Admin user created: admin@vibewrite.com / admin123")
    app.run(debug=True)