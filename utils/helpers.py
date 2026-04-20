from flask import request, url_for
from datetime import datetime, timedelta
import markdown
import os

def format_datetime(value, format='medium'):
    """Format datetime for templates"""
    if format == 'full':
        format = "%Y-%m-%d %H:%M:%S"
    elif format == 'medium':
        format = "%Y-%m-%d %H:%M"
    else:
        format = "%Y-%m-%d"
    return value.strftime(format)

def text_truncate(text, length=100, suffix='...'):
    """Truncate text to specified length"""
    if len(text) <= length:
        return text
    return text[:length].rsplit(' ', 1)[0] + suffix

def markdown_to_html(text):
    """Convert markdown text to HTML"""
    if not text:
        return ""
    return markdown.markdown(text, extensions=['fenced_code', 'tables'])

def get_file_extension(filename):
    """Get file extension from filename"""
    return os.path.splitext(filename)[1].lower()

def is_allowed_file(filename, allowed_extensions=None):
    """Check if file extension is allowed"""
    if allowed_extensions is None:
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    return get_file_extension(filename) in allowed_extensions

def calculate_read_time(text):
    """Calculate estimated read time for text"""
    words_per_minute = 200
    word_count = len(text.split())
    read_time = max(1, round(word_count / words_per_minute))
    return f"{read_time} min read"

def generate_excerpt(text, length=150):
    """Generate excerpt from text"""
    if not text:
        return ""
    # Remove markdown and HTML tags
    import re
    clean_text = re.sub(r'[#*`]', '', text)
    clean_text = re.sub(r'\[.*?\]\(.*?\)', '', clean_text)
    return text_truncate(clean_text.strip(), length)

def get_gravatar_url(email, size=80):
    """Generate Gravatar URL"""
    import hashlib
    email_hash = hashlib.md5(email.lower().encode('utf-8')).hexdigest()
    return f"https://www.gravatar.com/avatar/{email_hash}?s={size}&d=identicon"

def is_ajax_request():
    """Check if request is AJAX"""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'

def paginate_url(page, **kwargs):
    """Generate pagination URL"""
    args = request.args.copy()
    args['page'] = page
    args.update(kwargs)
    return url_for(request.endpoint, **args)

def award_points(user, points, badge_check=True):
    """Award points to user and check for badges"""
    from app import db
    user.points += points
    
    # Check for badge achievements
    if badge_check:
        if user.points >= 1000 and 'Veteran Writer' not in user.get_badges():
            user.add_badge('Veteran Writer')
        elif user.points >= 500 and 'Expert Writer' not in user.get_badges():
            user.add_badge('Expert Writer')
        elif user.points >= 100 and 'Prolific Writer' not in user.get_badges():
            user.add_badge('Prolific Writer')
    
    db.session.commit()

def get_popular_tags(limit=10):
    """Get most popular tags from posts"""
    from app import Post
    import collections
    import re
    
    all_tags = []
    posts = Post.query.filter_by(is_published=True).all()
    
    for post in posts:
        if post.tags:
            tags = [tag.strip().lower() for tag in post.tags.split(',')]
            all_tags.extend(tags)
    
    tag_counter = collections.Counter(all_tags)
    return tag_counter.most_common(limit)