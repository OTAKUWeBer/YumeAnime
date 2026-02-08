<div align="center">
  <img src="api/static/images/logo.png" alt="YumeAnime Logo" width="200">
  <h1>YumeAnime</h1>
  <p><strong>Your Ultimate Ad-Free Anime Streaming Experience</strong></p>
  
  <p>
    <a href="https://yume-animez.vercel.app/home"><strong>⛩️ YumeAnime</strong></a>
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

**YumeAnime** is **one of the few truly open-source** anime streaming platforms, built for fans who want a seamless and high-quality viewing experience. Powered by the Hianime provider, it offers a vast library of anime with a clean, responsive, and user-centric interface.

Unlike cluttered streaming sites, YumeAnime focuses on **comfort and usability**, offering features like automatic progress tracking, smart resume, and a customizable watch page.

## ✨ Key Features

- **🚫 Ad-Free Streaming**: Enjoy your favorite shows without interruptions.
- **📺 High-Quality Playback**: Fast streaming with multiple server options (HD-1, HD-2, Megaplay).
- **🔄 AniList Sync**: Automatically sync your watch progress with AniList. Never lose track of where you left off.
- **⏯️ Smart Resume**: The "Watch Now" button intelligently takes you to your last watched episode or the next one in the queue.
- **📱 Fully Responsive**: A premium experience on both Desktop and Mobile devices.
- **🎨 Modern UI/UX**:
    - **Glassmorphism Design**: Sleek, dark-themed aesthetics.
    - **Custom Watch Page**: Toggle between **List** and **Grid** views for episodes.
    - **Cinema Mode**: Focus on the anime with a distraction-free player.
    - **Auto-Scroll**: Sidebar automatically scrolls to your current episode.
- **🔎 Advanced Search**: instant search results with proper filtering.

## 🛠️ Tech Stack

- **Backend**: Python (Flask)
- **Frontend**: HTML5, CSS3 (Custom Variables), JavaScript (Vanilla)
- **Video Player**: Video.js with custom skinning and behavior
- **Data Source**: Hianime Scraper (Custom implementation)

## 🚀 Installation

Follow these steps to set up YumeAnime locally:

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/OTAKUWeBer/YumeAnime
    cd YumeAnime
    ```

2.  **Create a Virtual Environment**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set Up Environment Variables**
    Create a `.env` file in the root directory (use `example.env` as a reference):
    ```env
    FLASK_APP=run.py
    FLASK_ENV=development
    SECRET_KEY=your_secret_key_here
    
    # AniList Configuration (Optional, for sync)
    ANILIST_CLIENT_ID=your_anilist_client_id
    ANILIST_CLIENT_SECRET=your_anilist_client_secret
    ANILIST_REDIRECT_URI=http://localhost:5000/api/anilist/callback
    ```

5.  **Run the Application**
    ```bash
    python run.py
    ```
    Access the app at `http://localhost:5000`.

## ⚙️ Configuration

### AniList Integration
To enable AniList sync:
1.  Go to [AniList Developer Settings](https://anilist.co/settings/developer).
2.  Create a new client.
3.  Set the redirect URI to matches your deployment (e.g., `http://localhost:5000/api/anilist/callback`).
4.  Copy the Client ID and Secret to your `.env` file.

## 🤝 Contributing

We welcome contributions from the community! Whether it's fixing bugs, improving the UI, or adding new features, your help is appreciated.

1.  **Fork the Project**
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a **Pull Request**

## 📜 License

This project is open-source and available under the [MIT License](LICENSE).

---

<div align="center">
  <p>Made with ❤️ for the Anime Community</p>
</div>
