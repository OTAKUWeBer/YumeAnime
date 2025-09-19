# core/db_connector.py
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# Centralized MongoDB connection with optimizations
mongodb_uri = os.getenv("MONGODB_URI")
client = MongoClient(
    mongodb_uri,
    maxPoolSize=50,
    minPoolSize=5,
    compressors=['snappy', 'zlib']
)

# Provide access to the database and collections
db = client["test"]
users_collection = db["test"]
watchlist_collection = db["watchlist"]
