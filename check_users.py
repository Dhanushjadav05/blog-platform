import sqlite3
import os

def check_users():
    # Check both possible locations
    db_locations = [
        'vibewrite.db',                    # Root folder
        'instance/vibewrite.db'            # Instance folder
    ]
    
    for db_path in db_locations:
        if os.path.exists(db_path):
            print(f"🔍 Checking database: {db_path}")
            
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Check tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [table[0] for table in cursor.fetchall()]
                print(f"📋 Tables in {db_path}: {tables}")
                
                if 'user' in tables:
                    print("✅ User table found! Getting users...")
                    
                    # Get all users
                    cursor.execute("SELECT id, username, email, role, is_active FROM user")
                    users = cursor.fetchall()
                    
                    print(f"\n👥 FOUND {len(users)} USER(S) in {db_path}:")
                    print("=" * 70)
                    print(f"{'ID':<3} {'Username':<15} {'Email':<25} {'Role':<12} {'Status'}")
                    print("-" * 70)
                    
                    for user in users:
                        user_id, username, email, role, is_active = user
                        status = "✅ ACTIVE" if is_active else "❌ INACTIVE"
                        print(f"{user_id:<3} {username:<15} {email:<25} {role:<12} {status}")
                    
                    # Show role summary
                    print(f"\n📊 ROLE SUMMARY for {db_path}:")
                    cursor.execute("SELECT role, COUNT(*) FROM user GROUP BY role")
                    for role, count in cursor.fetchall():
                        print(f"  {role}: {count} user(s)")
                        
                    conn.close()
                    return  # Stop after finding the real database
                    
                else:
                    print(f"❌ No user table in {db_path}")
                    
                conn.close()
                
            except sqlite3.Error as e:
                print(f"❌ Database error with {db_path}: {e}")
        else:
            print(f"❌ Database not found: {db_path}")

if __name__ == "__main__":
    check_users()