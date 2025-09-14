# 🌸 Yume Anime

**Yume Anime** is an open-source Python web application built with **Flask**, allowing users to **search, browse, and stream anime episodes online**.
It now uses **HiAnime** as its source for anime data, providing a smooth, intuitive interface for exploring series, viewing episodes, and streaming directly in the browser.

🌐 **Live Demo:** [Yume Anime](https://yume-animez.vercel.app/home)

---

## 🏆 Features

* 🔍 **Anime Search** – Search for anime titles quickly.
* 📺 **Stream Episodes** – Watch episodes directly in the browser.
* ⏭️ **Episode Navigation** – Navigate seamlessly between next/previous episodes.
* 📊 **Anime Info** – Displays total episodes and series status (ongoing/completed).
* ⚡ **Custom 404 Page** – Friendly error handling for missing pages.

---

## 🛠️ Technology Stack

| Layer          | Technology                     |
| -------------- | ------------------------------ |
| **Frontend**   | HTML, CSS, Jinja2 (templating) |
| **Backend**    | Python, Flask                  |
| **Scraping**   | Custom HiAnime scraper         |
| **Deployment** | Vercel                         |

---

## 🚀 Getting Started

### Prerequisites

* Python 3.9+
* `pip` package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/OTAKUWeBer/YumeAnime.git
cd YumeAnime

# Install dependencies
pip install -r requirements.txt
```

### Running the App

Run with either command:

```bash
# Using Flask
flask run

# Or using the main script
python run.py
```

Visit: `http://127.0.0.1:5000/`

---

## 📌 Roadmap

* Improve mobile responsiveness
* Optimize HiAnime scraping & caching
* Add user accounts & watchlists (future enhancement)

---

## 📝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/YourFeature`)
3. Commit your changes (`git commit -m 'Add YourFeature'`)
4. Push to the branch (`git push origin feature/YourFeature`)
5. Open a Pull Request

Please follow [PEP8](https://www.python.org/dev/peps/pep-0008/) coding standards and write clear commit messages.

---

## 📜 License

This project is **MIT Licensed** – see the [LICENSE](LICENSE) file for details.

---

## ❤️ Acknowledgements

* [HiAnime](https://hianime.to/) – Source of anime data
* Flask community for excellent documentation and support

---

✨ **Thank you for visiting Yume Anime!**
Contributions, feedback, and ideas are always welcome.
