<div align="center">
  <img src="api/static/images/logos/logo.png" alt="YumeZone Logo" width="200">
  <h1>YumeZone</h1>
  <p><strong>Your Ultimate Ad-Free Anime & Manga Streaming Experience</strong></p>
  
  <p>
    <a href="https://yumezone.vercel.app/home"><strong>⛩️ YumeZone</strong></a>
  </p>

  <p>
    <a href="#-key-features">Features</a> •
    <a href="#%EF%B8%8F-tech-stack">Tech Stack</a> •
    <a href="#-installation">Installation</a> •
    <a href="#-contributing">Contributing</a>
  </p>
</div>

---

## 📖 Introduction

**YumeZone** is a highly polished, feature-rich anime & manga platform built for fans who want a seamless, ad-free experience. It hooks into AniList and MyAnimeList and utilizes the Miruro API to provide a comprehensive anime library — along with a fully integrated manga reader — all wrapped in a gorgeous Glassmorphism user interface.

Our focus is entirely on usability, speed, and cross-platform consistency.

## ✨ Key Features

- **🚫 Ad-Free Streaming & Reading**: Pure entertainment without popups, redirects, or visual clutter.
- **📺 High-Quality Playback**: Fast streaming with multiple server options, subtitle/audio toggles, and quality selectors natively baked into the player.
- **⏭️ Intro & Outro Skip**: Smart episode intro and outro detection on the anime info page — skip straight to the action or the next episode with a single click.
- **📚 Manga Reader**: Browse, search, and read manga directly on YumeZone with a clean, distraction-free chapter reader.
- **🔄 Two-Way Tracker Sync**: Link **AniList** and **MyAnimeList** accounts! The player will automatically update your viewing progress seamlessly in the background as you watch.
- **💬 Live Comments & Reactions**: Express yourself on episodes using the custom-built nested comment system with integrated GIF support. Drop quick "likes" or "dislikes" on comments and specific episodes.
- **⏯️ Smart Resume**: Intelligent tracking remembers exactly what episode you were on. "Watch Now" will instantly drop you back into the action.
- **🎨 Modern UI/UX**:
    - **Glassmorphism Design**: Sleek, immersive dark-themed presentation.
    - **Spotlight Carousel**: Discover tracking information, genres, ratings, and studios right from the top page.
    - **Cinema Mode**: Distraction-free, immersive video player layout.
    - **Fully Responsive**: A premium and consistent experience whether you are on Desktop, Tablet, or Mobile.
- **🔐 Secure Authentication**: Includes full user accounts, password recovery flow via email, Turnstile bot protection, and more.
- **🔎 Advanced Discoverability**: Deep search, category filtering, schedule countdowns, and genre exploration — for both anime and manga.

## 🛠️ Tech Stack

- **Backend**: Python (Flask, Async/Await)
- **Frontend**: HTML5, CSS3 (Vanilla / Custom Variables), JavaScript
- **Video Player**: Video.js with specialized integrations
- **Database**: MongoDB (User accounts, watch history, caching logic)
- **Data & Streaming APIs**: Miruro Native API, AniList GraphQL, MyAnimeList OAuth API
- **Security**: Cloudflare Turnstile, Bcrypt Password Hashing, Session Versioning

## 🚀 Installation & Local Development

Ready to run YumeZone locally? Follow these steps:

1. **Clone the Repository**
    ```bash
    git clone https://github.com/OTAKUWeBer/YumeZone
    cd YumeZone
    ```

2. **Create a Virtual Environment**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3. **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4. **Set Up Environment Variables**
    Duplicate `.env.example` and rename it to `.env`. Fill in the required parameters:
    ```env
    # ==============================================================================
    # Security & App Config
    # ==============================================================================
    # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    FLASK_KEY="YOUR_RANDOM_FLASK_SECRET_KEY"
    # Internal API key — generate the same way as FLASK_KEY
    API_KEY="YOUR_GENERATED_API_KEY"
    # Comma-separated allowed origins for CORS
    ALLOWED_ORIGINS="https://your-app.app,http://localhost:5000"

    # ==============================================================================
    # Database Configuration (MongoDB)
    # ==============================================================================
    MONGODB_URI="mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority&appName=YourApp"
    db="name_of_your_database"
    users_collection="name_of_your_users_collection"
    watchlist_collection="name_of_your_watchlist_collection"
    comments_collection="comments"
    episode_reactions_collection="episode_reactions"

    # ==============================================================================
    # Streaming & Scraping Services
    # ==============================================================================
    MIRURO_API_URL="https://api.your-domain.com/"
    PROXY_URL="https://proxy.your-domain.com/proxy/"

    # ==============================================================================
    # Captcha / Bot Protection (Cloudflare Turnstile)
    # ==============================================================================
    # Get from: Cloudflare Dashboard → Turnstile → Add Site
    CLOUDFLARE_SECRET="YOUR_CLOUDFLARE_SECRET"
    CF_SITE_KEY="YOUR_CF_SITE_KEY"

    # ==============================================================================
    # Email Configuration (SMTP) — For Password Resets
    # ==============================================================================
    # Google Account → Security → 2-Step Verification → App passwords
    GMAIL_USER="your-email@gmail.com"
    GMAIL_APP_PASSWORD="your-16-char-app-password"

    # ==============================================================================
    # OAuth Integrations: AniList
    # ==============================================================================
    # Create an API client at: https://anilist.co/settings/developer
    ANILIST_CLIENT_ID="YOUR_ANILIST_CLIENT_ID"
    ANILIST_CLIENT_SECRET="YOUR_ANILIST_CLIENT_SECRET"
    ANILIST_REDIRECT_URI="https://your-domain.com/auth/anilist/callback"

    # ==============================================================================
    # OAuth Integrations: MyAnimeList
    # ==============================================================================
    # Create an API client at: https://myanimelist.net/apiconfig (select "Web" App Type)
    MAL_CLIENT_ID="YOUR_MAL_CLIENT_ID"
    MAL_CLIENT_SECRET="YOUR_MAL_CLIENT_SECRET"
    MAL_REDIRECT_URI="https://your-domain.com/auth/mal/callback"
    ```

5. **Run the Application**
    ```bash
    python run.py
    ```
    Access the application right from your browser at `http://localhost:5000`.

## ⚙️ Integrations Setup Notes

- **Miruro API**: You'll need access to a Miruro-compatible data API instance for anime indexing and m3u8 stream resolution.
- **AniList & MyAnimeList**: Go to their respective Developer Portals, create a new application, and match the OAuth Redirect URIs to your `.env` values.
- **Cloudflare Turnstile**: Log into the [Cloudflare Dashboard](https://dash.cloudflare.com/) → **Turnstile** → **Add Site**. Copy the **Site Key** into `CF_SITE_KEY` and the **Secret Key** into `CLOUDFLARE_SECRET`. Make sure your production domain is listed as an allowed hostname in the Turnstile widget settings.
- **API Key**: `API_KEY` is used for internal service-to-service security. Generate a strong random string the same way as `FLASK_KEY` — keep it secret and never commit it to version control.
- **Passwords via Gmail**: You'll need to generate a Google App Password for the application to dispatch secure password reset tokens. Go to **Google Account → Security → 2-Step Verification → App passwords**.

## 🤝 Contributing

We welcome community contributions! Found a bug, or have a UI polish idea? Read our setup to dive in:

1. **Fork the Project**
2. Create your Feature Branch (`git checkout -b feature/CoolNewAddition`)
3. Commit your Changes (`git commit -m 'feat: Add a new custom player skin'`)
4. Push to the Branch (`git push origin feature/CoolNewAddition`)
5. Open a **Pull Request**

## 📜 License

This project is open-source and available under the [MIT License](LICENSE).

---

<div align="center">
  <p>Made with ❤️ for the Anime & Manga Community</p>
</div>