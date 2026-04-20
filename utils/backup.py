import os
import json
import zipfile
from datetime import datetime
from app import User, Post, Comment, Ad, Backup
from app import db

class BackupManager:
    def __init__(self, app=None):
        self.app = app
    
    def init_app(self, app):
        self.app = app
    
    def create_backup(self, backup_type='full'):
        """Create a backup of the specified data"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = self.app.config.get('BACKUP_FOLDER', 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            backup_data = {}
            
            if backup_type in ['full', 'users']:
                backup_data['users'] = self._export_users()
            
            if backup_type in ['full', 'posts']:
                backup_data['posts'] = self._export_posts()
                backup_data['comments'] = self._export_comments()
            
            if backup_type in ['full', 'ads']:
                backup_data['ads'] = self._export_ads()
            
            # Save JSON backup
            json_filename = f"vibewrite_{backup_type}_{timestamp}.json"
            json_path = os.path.join(backup_dir, json_filename)
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
            
            # Create zip file
            zip_filename = f"vibewrite_{backup_type}_{timestamp}.zip"
            zip_path = os.path.join(backup_dir, zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                zipf.write(json_path, json_filename)
            
            # Clean up JSON file
            os.remove(json_path)
            
            # Create backup record
            backup = Backup(
                filename=zip_filename,
                file_path=zip_path,
                backup_type=backup_type,
                file_size=self._get_file_size(zip_path)
            )
            
            db.session.add(backup)
            db.session.commit()
            
            return backup
            
        except Exception as e:
            print(f"Backup creation error: {e}")
            return None
    
    def _export_users(self):
        users = User.query.all()
        return [{
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'bio': user.bio,
            'points': user.points,
            'badges': user.get_badges(),
            'created_at': user.created_at.isoformat(),
            'is_active': user.is_active
        } for user in users]
    
    def _export_posts(self):
        posts = Post.query.all()
        return [{
            'id': post.id,
            'title': post.title,
            'content': post.content,
            'excerpt': post.excerpt,
            'visibility': post.visibility,
            'tags': post.tags,
            'category': post.category,
            'author_id': post.user_id,
            'author_username': post.author.username,
            'created_at': post.created_at.isoformat(),
            'updated_at': post.updated_at.isoformat(),
            'is_published': post.is_published,
            'like_count': post.like_count(),
            'comment_count': post.comment_count()
        } for post in posts]
    
    def _export_comments(self):
        comments = Comment.query.all()
        return [{
            'id': comment.id,
            'content': comment.content,
            'user_id': comment.user_id,
            'username': comment.user.username,
            'post_id': comment.post_id,
            'post_title': comment.post.title,
            'created_at': comment.created_at.isoformat(),
            'is_approved': comment.is_approved
        } for comment in comments]
    
    def _export_ads(self):
        ads = Ad.query.all()
        return [{
            'id': ad.id,
            'title': ad.title,
            'content': ad.content,
            'image_url': ad.image_url,
            'target_url': ad.target_url,
            'ad_type': ad.ad_type,
            'status': ad.status,
            'clicks': ad.clicks,
            'impressions': ad.impressions,
            'budget': ad.budget,
            'advertiser_id': ad.user_id,
            'advertiser_username': ad.advertiser.username,
            'start_date': ad.start_date.isoformat() if ad.start_date else None,
            'end_date': ad.end_date.isoformat() if ad.end_date else None,
            'created_at': ad.created_at.isoformat()
        } for ad in ads]
    
    def _get_file_size(self, filepath):
        size = os.path.getsize(filepath)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def restore_backup(self, backup_id):
        """Restore data from a backup"""
        # Implementation for restore functionality
        pass
    
    def auto_backup(self):
        """Perform automatic backup based on schedule"""
        if self.app.config.get('ENABLE_BACKUPS', True):
            return self.create_backup('full')
        return None