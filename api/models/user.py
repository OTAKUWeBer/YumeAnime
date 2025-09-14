import random
from datetime import datetime
from bcrypt import hashpw, gensalt, checkpw
from ..core.db_connector import users_collection 


def generate_unique_id():
    """Generate a unique 6-digit ID for a user."""
    while True:
        _id = random.randint(100000, 999999)
        if users_collection.find_one({"_id": _id}) is None:
            return _id

def create_user(username, password, email=None):
    """Create a new user with a unique ID, including email support."""
    _id = generate_unique_id()
    hashed_password = hashpw(password.encode('utf-8'), gensalt())
    
    user_doc = {
        "_id": _id,
        "username": username,
        "password": hashed_password,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Add email if provided
    if email:
        user_doc["email"] = email
    
    users_collection.insert_one(user_doc)
    return _id  # Return the new user's ID

def create_anilist_user(anilist_user_info, access_token):
    """Create a new user from AniList OAuth data."""
    _id = generate_unique_id()
    
    # Extract user information from AniList data
    username = anilist_user_info['name']
    anilist_id = anilist_user_info['id']
    avatar = anilist_user_info.get('avatar', {}).get('large') or anilist_user_info.get('avatar', {}).get('medium')
    
    # Prepare statistics if available
    stats = {}
    if 'statistics' in anilist_user_info and 'anime' in anilist_user_info['statistics']:
        anime_stats = anilist_user_info['statistics']['anime']
        stats = {
            'anime_count': anime_stats.get('count', 0),
            'mean_score': anime_stats.get('meanScore', 0),
            'minutes_watched': anime_stats.get('minutesWatched', 0)
        }
    
    user_doc = {
        "_id": _id,
        "username": username,
        "anilist_id": anilist_id,
        "anilist_access_token": access_token,
        "avatar": avatar,
        "anilist_stats": stats,
        "banner_image": anilist_user_info.get('bannerImage'),
        "about": anilist_user_info.get('about'),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "auth_method": "anilist"
    }
    
    users_collection.insert_one(user_doc)
    return _id

def update_anilist_user(user_id, anilist_user_info, access_token):
    """Update existing user with latest AniList information."""
    avatar = anilist_user_info.get('avatar', {}).get('large') or anilist_user_info.get('avatar', {}).get('medium')
    
    # Prepare statistics if available
    stats = {}
    if 'statistics' in anilist_user_info and 'anime' in anilist_user_info['statistics']:
        anime_stats = anilist_user_info['statistics']['anime']
        stats = {
            'anime_count': anime_stats.get('count', 0),
            'mean_score': anime_stats.get('meanScore', 0),
            'minutes_watched': anime_stats.get('minutesWatched', 0)
        }
    
    update_doc = {
        "$set": {
            "anilist_access_token": access_token,
            "avatar": avatar,
            "anilist_stats": stats,
            "banner_image": anilist_user_info.get('bannerImage'),
            "about": anilist_user_info.get('about'),
            "updated_at": datetime.utcnow()
        }
    }
    
    users_collection.update_one({"_id": user_id}, update_doc)
    return True

def get_user_by_anilist_id(anilist_id):
    """Get user by AniList ID."""
    return users_collection.find_one({"anilist_id": anilist_id})

def get_user(username, password):
    """Retrieve a user by username and password."""
    user = users_collection.find_one({"username": username})
    if user and user.get('password') and checkpw(password.encode('utf-8'), user['password']):
        return user
    return None

def get_user_by_id(_id):
    """Get user by ID."""
    return users_collection.find_one({"_id": _id})

def get_user_by_email(email):
    """Get user by email."""
    return users_collection.find_one({"email": email})

def user_exists(username):
    """Check if a user with the given username already exists."""
    return users_collection.find_one({"username": username}) is not None

def email_exists(email):
    """Check if a user with the given email already exists."""
    if not email:
        return False
    return users_collection.find_one({"email": email}) is not None

def update_user_avatar(_id, avatar_url):
    """Update user's avatar."""
    users_collection.update_one(
        {"_id": _id},
        {
            "$set": {
                "avatar": avatar_url,
                "updated_at": datetime.utcnow()
            }
        }
    )

def update_user_email(_id, email):
    """Update user's email if it doesn't already exist."""
    if email_exists(email):
        return False  # Email already taken
    
    users_collection.update_one(
        {"_id": _id},
        {
            "$set": {
                "email": email,
                "updated_at": datetime.utcnow()
            }
        }
    )
    return True

def change_password(_id, old_password, new_password):
    """Change user's password after verifying old password."""
    user = get_user_by_id(_id)
    if not user or not user.get('password'):
        return False
    
    # Verify old password
    if not checkpw(old_password.encode('utf-8'), user['password']):
        return False
    
    # Hash new password
    new_hashed_password = hashpw(new_password.encode('utf-8'), gensalt())
    
    # Update password
    users_collection.update_one(
        {"_id": _id},
        {
            "$set": {
                "password": new_hashed_password,
                "updated_at": datetime.utcnow()
            }
        }
    )
    return True

def delete_user(_id):
    """Delete a user by ID."""
    result = users_collection.delete_one({"_id": _id})
    return result.deleted_count > 0

def get_all_users():
    """Get all users (for admin purposes - exclude passwords)."""
    return list(users_collection.find({}, {"password": 0}))

def get_user_count():
    """Get total number of users."""
    return users_collection.count_documents({})

# Additional utility functions for user management

def search_users(query, limit=10):
    """Search users by username or email."""
    search_filter = {
        "$or": [
            {"username": {"$regex": query, "$options": "i"}},
            {"email": {"$regex": query, "$options": "i"}}
        ]
    }
    return list(users_collection.find(search_filter, {"password": 0}).limit(limit))

def get_recent_users(limit=10):
    """Get recently registered users."""
    return list(users_collection.find({}, {"password": 0})
                .sort("created_at", -1)
                .limit(limit))

def link_anilist_to_existing_user(user_id, anilist_user_info, access_token):
    """
    Link an AniList account to an existing user.

    Args:
        user_id (int): Existing user’s internal ID (_id).
        anilist_user_info (dict): AniList user information (from AniList API).
        access_token (str): AniList OAuth access token.

    Returns:
        bool: True if updated successfully, False otherwise.
    """
    user = get_user_by_id(user_id)
    if not user:
        return False  # User not found

    # Prevent linking if AniList ID is already linked to another account
    existing = get_user_by_anilist_id(anilist_user_info['id'])
    if existing and existing['_id'] != user_id:
        return False  # AniList account already linked elsewhere

    avatar = anilist_user_info.get('avatar', {}).get('large') or anilist_user_info.get('avatar', {}).get('medium')

    stats = {}
    if 'statistics' in anilist_user_info and 'anime' in anilist_user_info['statistics']:
        anime_stats = anilist_user_info['statistics']['anime']
        stats = {
            'anime_count': anime_stats.get('count', 0),
            'mean_score': anime_stats.get('meanScore', 0),
            'minutes_watched': anime_stats.get('minutesWatched', 0)
        }

    update_doc = {
        "$set": {
            "anilist_id": anilist_user_info['id'],
            "anilist_access_token": access_token,
            "avatar": avatar,
            "anilist_stats": stats,
            "banner_image": anilist_user_info.get('bannerImage'),
            "about": anilist_user_info.get('about'),
            "updated_at": datetime.utcnow(),
            "auth_method": "anilist_linked"
        }
    }

    users_collection.update_one({"_id": user_id}, update_doc)
    return True

def unlink_anilist_from_user(user_id: str) -> bool:
    """Remove AniList credentials from a user."""
    result = users_collection.update_one(
        {"_id": user_id},
        {"$unset": {
            "anilist_access_token": "",
            "anilist_refresh_token": "",
            "anilist_expires_at": ""
        }}
    )
    return result.modified_count > 0