# VibeWrite

A modern, feature-rich blog platform built with Flask. VibeWrite supports multiple user roles (readers, authors, advertisers, and admins), gamification, advertising, and a beautiful responsive interface.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.3.3-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## Features

### Core Blog Features
- **Multi-role User System**: Reader, Author, Advertiser, and Admin roles
- **Rich Text Editing**: Markdown support with live embeds for YouTube, Spotify, Instagram, and Twitter/X
- **Post Management**: Create, edit, and manage blog posts with visibility options (public, private, password-protected)
- **Media Uploads**: Featured image uploads for posts
- **Categories & Tags**: Organize content with categorization and tagging
- **Comments System**: Readers can comment on posts
- **Likes System**: Like/unlike posts with engagement tracking
- **Reading Time**: Automatic reading time estimation for posts

### Gamification System
- **XP & Levels**: Readers earn XP and level up through engagement
- **Writer Tiers**: Bronze → Silver → Gold tier progression for authors
- **Reading Streaks**: Track consecutive reading days with freeze tokens
- **Daily Login Rewards**: Earn XP for daily visits
- **Badge System**: Earn badges for milestones (posts, comments, likes, points)

### Advertising Platform
- **Ad Management**: Advertisers can create and manage ad campaigns
- **Multiple Ad Types**: Banner, sidebar, and inline ads
- **Featured Home Ads**: Premium placement on homepage
- **Analytics**: Track clicks, impressions, and CTR
- **Budget System**: Set and manage ad budgets with cost-per-impression pricing

### Admin Features
- **User Management**: View and manage all platform users
- **Ad Moderation**: Approve or reject submitted advertisements
- **Backup System**: Create full, posts-only, or users-only backups
- **Dashboard Analytics**: Overview of platform activity and metrics

### User Features
- **Reader Dashboard**: Personalized feed, bookmarks, and reading history
- **Author Dashboard**: Post management, analytics, and writer stats
- **Advertiser Dashboard**: Campaign management and performance metrics
- **User Profiles**: Customizable profiles with avatars and bios
- **Search Functionality**: Search posts by title, content, tags, or category
- **Leaderboards**: View top authors and readers

### Technical Features
- **Responsive Design**: Mobile-friendly Bootstrap interface
- **Image Lightbox**: GLightbox integration for post galleries
- **Auto-embeds**: Automatic embedding of media links (YouTube, Spotify, Instagram, X/Twitter)
- **Password Protection**: Private posts with password access
- **Secure Authentication**: Password hashing with Werkzeug
- **CSRF Protection**: Form security with Flask-WTF

## Tech Stack

- **Backend**: Flask 2.3.3
- **Database**: SQLite with SQLAlchemy ORM
- **Authentication**: Flask-Login
- **Forms**: Flask-WTF with CSRF protection
- **Templating**: Jinja2 with custom filters (Markdown support)
- **Frontend**: Bootstrap 5, vanilla JavaScript
- **Image Processing**: Pillow

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/Dhanushjadav05/blog-platform-.git
   cd blog-platform-
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the application**
   ```bash
   python run.py
   ```

6. **Access the application**
   Open your browser and navigate to `http://localhost:5000`

## Project Structure

```
VibeWrite/
├── app.py                 # Main application file with models and routes
├── config.py             # Configuration settings
├── run.py                # Application entry point
├── requirements.txt      # Python dependencies
├── vibewrite.db          # SQLite database (created on first run)
├── backups/              # Backup files directory
├── static/
│   ├── css/             # Custom stylesheets
│   ├── js/              # JavaScript files
│   ├── uploads/         # User uploaded images
│   └── images/          # Static images
└── templates/
    ├── base.html        # Base template with navigation
    ├── index.html       # Homepage
    ├── auth/            # Login & registration templates
    ├── reader/          # Reader dashboard, feed, search
    ├── author/          # Post creation and management
    ├── advertiser/      # Ad management templates
    ├── admin/           # Admin dashboard and management
    └── 404.html, 500.html  # Error pages
```

## User Roles

### Reader
- Browse and read published posts
- Search for content
- Comment on posts
- Like posts
- Track reading streaks and earn XP
- View personalized feed

### Author
- All reader features
- Create, edit, and delete blog posts
- Upload featured images
- Set post visibility and passwords
- View post analytics (views, likes, comments)
- Earn writer XP and tier up (Bronze → Silver → Gold)

### Advertiser
- Create and manage ad campaigns
- Choose ad types (banner, sidebar, inline)
- Set budgets and target URLs
- View ad performance metrics (clicks, impressions, CTR)
- Featured home page placement option

### Admin
- All platform features
- User management (view, edit roles)
- Ad moderation (approve/reject)
- Create system backups
- Platform analytics overview

## Gamification Points

| Action | XP Awarded |
|--------|-----------|
| Daily Login | 2 XP |
| Reading a Post | 5 XP |
| Liking a Post | 1 XP |
| Commenting | 3 XP |
| Creating a Post | 20 XP |
| Post Receiving 10 Likes | 10 XP (Author) |
| Post Receiving 10 Comments | 10 XP (Author) |

### Writer Tiers
- **Bronze**: 0-199 XP
- **Silver**: 200-599 XP
- **Gold**: 600+ XP

### Reader Levels
Level up as you earn XP with milestones at 100, 250, 500, 900, 1400, and 2000 XP.

## Available Badges

- First Post, 5 Posts, 10 Posts
- First Comment, 10 Comments
- First Like, 50 Likes Given
- 100 Points, 250 Points, 500 Points
- Post 10 Likes, Post 50 Likes
- Post 10 Comments, Post 50 Comments

## Configuration

Edit `config.py` to customize:

```python
# Security
SECRET_KEY = 'your-secret-key-here'

# Database
SQLALCHEMY_DATABASE_URI = 'sqlite:///vibewrite.db'

# Uploads
UPLOAD_FOLDER = 'static/uploads'
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

# Backups
BACKUP_FOLDER = 'backups'
AUTO_BACKUP_DAYS = 7

# Feature Flags
ENABLE_GAMIFICATION = True
ENABLE_BACKUPS = True
ENABLE_ADS = True
```

## API Endpoints

The application includes various REST-style endpoints:

- `POST /like/<post_id>` - Like/unlike a post
- `POST /ads/<ad_id>/click` - Track ad click
- `GET /api/search?q=<query>` - Search posts

## Security Features

- Password hashing with Werkzeug
- CSRF protection on all forms
- Secure file upload validation
- SQL injection protection via SQLAlchemy ORM
- XSS protection through template auto-escaping

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License.

## Acknowledgments

- Built with [Flask](https://flask.palletsprojects.com/)
- UI powered by [Bootstrap](https://getbootstrap.com/)
- Icons from [Bootstrap Icons](https://icons.getbootstrap.com/)
- Lightbox by [GLightbox](https://biati-digital.github.io/glightbox/)

---

**VibeWrite** - Share your vibe with the world!
