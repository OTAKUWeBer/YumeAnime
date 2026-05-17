# 🛡️ YumeZone API Rate Limiting Reference

This document provides a comprehensive guide to all API rate limits configured across the YumeZone platform. Rate limiting is powered by **Flask-Limiter** using client IP address tracking (`get_remote_address`) to protect the platform from abuse, brute-force attacks, and spam.

---

## 🔑 Authentication Endpoints (`auth_api`)

These endpoints protect critical account security actions. They are heavily rate-limited to prevent brute-force login and account registration abuse.

| Endpoint | Method | Rate Limit | Description |
| :--- | :---: | :--- | :--- |
| `/api/auth/signup` | `POST` | **3 per minute** | User registration / account creation. |
| `/api/auth/login` | `POST` | **5 per minute** | User authentication / login. |
| `/api/auth/forgot-password` | `POST` | **3 per minute** | Requests a 6-digit verification code to the user's email. |
| `/api/auth/verify-reset-code`| `POST` | **5 per minute** | Validates the 6-digit numeric reset code. |
| `/api/auth/reset-password` | `POST` | **3 per minute** | Resets user password after verification. |
| `/api/auth/check-username` | `GET` | **60 per minute** | Real-time username availability checker. |

---

## 💬 Comments & Reactions (`comments_api`)

These limits prevent comment section spamming, automated script posting, and reaction gaming.

| Endpoint | Method | Rate Limit | Description |
| :--- | :---: | :--- | :--- |
| `/api/comments` | `POST` | **4 per minute** | Creating a new top-level comment. |
| `/api/comments/<id>/reply` | `POST` | **4 per minute** | Replying to an existing comment. |
| `/api/comments/<id>` | `PUT` | **4 per minute** | Editing a comment (only allowed within 5 minutes). |
| `/api/comments/<id>` | `DELETE` | **10 per minute** | Soft/hard deleting a user's own comment. |
| `/api/comments/<id>/react` | `POST` | **30 per minute** | Toggling a like/dislike on a comment. |
| `/api/episodes/reaction` | `POST` | **30 per minute** | Toggling a like/dislike on an episode. |

---

## 👥 Watch Together Room Controls (`watch_together`)

These endpoints control watch together multiplayer sessions, room state syncing, and room chats.

| Endpoint | Method | Rate Limit | Description |
| :--- | :---: | :--- | :--- |
| `/api/watch-together/rooms` | `POST` | **3 per minute** | Creating a new watch together room. |
| `/api/watch-together/rooms/<id>/join` | `POST` | **10 per minute** | Joining an active watch together room. |
| `/api/watch-together/rooms/<id>/events` | `POST` | **60 per minute** | Real-time event synchronization and chat messages inside a room. |

---

## 🛡️ Admin & Moderation Endpoints (`admin_api`)

These endpoints are restricted to **Moderators (`mod`)** and **Admins (`admin`)** only, with the exception of the reporting endpoint, which is available to all logged-in users.

| Endpoint | Method | Rate Limit | Required Role | Description |
| :--- | :---: | :--- | :---: | :--- |
| `/api/admin/report-comment` | `POST` | **5 per minute** | Logged-in | Submit a report flagging a comment. |
| `/api/admin/users/<id>/role` | `POST` | **10 per minute** | `admin` | Promotes/demotes user roles. |
| `/api/admin/users/<id>/ban` | `POST` | **10 per minute** | `admin` | Bans or unbans a user account. |
| `/api/admin/users/<id>/mute` | `POST` | **10 per minute** | `mod` or `admin` | Mutes or unmutes a user. |
| `/api/admin/reports/<id>/resolve` | `POST` | **20 per minute** | `mod` or `admin` | Resolves a pending flag. |
| `/api/admin/reports/<id>/ignore` | `POST` | **20 per minute** | `mod` or `admin` | Ignores/dismisses a flag. |
| `/api/admin/reports/<id>/delete-comment` | `POST` | **20 per minute** | `mod` or `admin` | Moderation comment deletion via reports list. |
| `/api/admin/comments/<id>/delete` | `POST` | **30 per minute** | `mod` or `admin` | General moderator comment deletion power. |

---

## ⚙️ Technical Details

* **Identifier**: Client IP address (`key_func=get_remote_address`).
* **Fallback Storage**: In-memory database (development) / Redis (production).
* **Response Status**: When a limit is breached, the API immediately returns `HTTP 429 Too Many Requests` with a JSON payload explaining the cooldown period.
