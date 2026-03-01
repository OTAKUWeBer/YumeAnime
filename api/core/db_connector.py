# core/db_connector.py
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

db_name = os.getenv("db", "yumeanime")
users_collection_name = os.getenv("users_collection", "users")
watchlist_collection_name = os.getenv("watchlist_collection", "watchlist")

# Centralized MongoDB connection with optimizations
mongodb_uri = os.getenv("MONGODB_URI")
client = MongoClient(
    mongodb_uri,
    maxPoolSize=50,
    minPoolSize=5,
    compressors=['snappy', 'zlib']
)

# Provide access to the database and collections
db = client[db_name]
users_collection = db[users_collection_name]
watchlist_collection = db[watchlist_collection_name]
