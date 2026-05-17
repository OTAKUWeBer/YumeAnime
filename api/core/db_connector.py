# core/db_connector.py
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

db_name = os.getenv("db", "yume-userdata")
users_collection_name = os.getenv("users_collection", "users")
watchlist_collection_name = os.getenv("watchlist_collection", "watchlist")
comments_collection_name = os.getenv("comments_collection", "comments")
episode_reactions_collection_name = os.getenv("episode_reactions_collection", "episode_reactions")
watch_together_rooms_collection_name = os.getenv("watch_together_rooms_collection", "watch_together_rooms")
watch_together_messages_collection_name = os.getenv("watch_together_messages_collection", "watch_together_messages")
reports_collection_name = os.getenv("reports_collection", "reports")
audit_log_collection_name = os.getenv("audit_log_collection", "audit_log")

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
comments_collection = db[comments_collection_name]
episode_reactions_collection = db[episode_reactions_collection_name]
watch_together_rooms_collection = db[watch_together_rooms_collection_name]
watch_together_messages_collection = db[watch_together_messages_collection_name]
reports_collection = db[reports_collection_name]
audit_log_collection = db[audit_log_collection_name]
