from pymongo import MongoClient
import random
from bcrypt import hashpw, gensalt, checkpw
from dotenv import load_dotenv
import os

load_dotenv()

# Retrieve MongoDB URI from environment variables
mongodb_uri = os.getenv("MONGODB_URI")

# Connect to MongoDB using the URI from the environment
client = MongoClient(mongodb_uri)
db = client["test"]
users_collection = db["test"]

def generate_unique_id():
    """Generate a unique 6-digit ID for a user."""
    while True:
        _id = random.randint(100000, 999999)
        if users_collection.find_one({"_id": _id}) is None:
            return _id

def create_user(username, password):
    """Create a new user with a unique ID."""
    _id = generate_unique_id()
    hashed_password = hashpw(password.encode('utf-8'), gensalt())
    users_collection.insert_one({"username": username, "password": hashed_password, "_id": _id})
    return _id  # Return the new user's ID or success message

def get_user(username, password):
    """Retrieve a user by username and password."""
    user = users_collection.find_one({"username": username})
    if user and checkpw(password.encode('utf-8'), user['password']):
        return user
    return None

def user_exists(username):
    """Check if a user already exists."""
    return users_collection.find_one({"username": username}) is not None
