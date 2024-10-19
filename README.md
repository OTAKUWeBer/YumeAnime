# Yume Animez

**Yume Animez** is a Python-based web application built using Flask that allows users to search, browse, and stream anime episodes. It scrapes data from the **GogoAnime** website, providing users with an intuitive interface to explore anime series, view available episodes, and watch them directly within the app.

## Website URL
- Live Site: [Yume Animez](https://yume-animez.vercel.app/home)

## Features
- **Anime Search**: Users can search for their favorite anime and view available episodes.
- **Episode Navigation**: View details of individual episodes and navigate between them using next/previous buttons.
- **Watch Episodes**: Stream anime episodes directly from the site.
- **Error Handling**: User-friendly error messages and a custom 404 page.
- **Anime Status**: Displays the status and total episodes available for each anime series.

## Tech Stack
- **Backend**: Python, Flask
- **Frontend**: HTML, CSS, Jinja2 for templating
- **Web Scraping**: Custom scraper using `GogoAnimeScraper`
- **Deployment**: Vercel

## Installation & Setup

1. **Clone the Repository**
   ```bash
   git clone https://github.com/OTAKUWeBer/YumeAnime
   cd YumeAnime
   ```

2. **Create and Activate a Virtual Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up Environment Variables** (Optional)
   - Update the Flask `secret_key` if needed in `app.py`:
     ```python
     app.secret_key = 'YourSecretKey'
     ```

5. **Run the Application**
   ```bash
   flask run
   ```
   The app will run locally at `http://127.0.0.1:5000`.

## Project Structure

```

.
├── api/
│   ├── app.py                   # Main Flask application
│   ├── scrapers/                # Directory for web scraping logic
│   │   ├── gogo.py              # GogoAnimeScraper implementation
│   │   ├── __init__.py          # Scraper initialization
│   │   └── __pycache__/         # Compiled Python files (ignored in version control)
│   ├── static/                  # Static assets (CSS, images, etc.)
│   │   └── images/              # Directory for images
│   │       ├── logo.png         # Site logo
│   │       └── rm_logo.png      # Additional logo
│   └── templates/               # HTML templates for the site
│       ├── 404.html             # Custom 404 error page
│       ├── base.html            # Base HTML template
│       ├── episodes.html        # Episode listing template
│       ├── index.html           # Homepage template
│       ├── results.html         # Search results template
│       └── watch.html           # Episode streaming template
├── README.md                    # Project documentation
├── requirements.txt             # Python dependencies
└── vercel.json                  # Vercel deployment configuration

```

## API Routes

### Home Page
- **Route**: `/home`
- **Method**: `GET`
- Fetches and displays anime suggestions for users to explore.

### Search Anime
- **Route**: `/search?q=<anime_name>`
- **Method**: `GET`
- Users can search for anime, and the results are displayed on the search results page.

### Anime Episodes
- **Route**: `/episodes/<anime_title>`
- **Method**: `GET`
- Displays the list of episodes for the selected anime.

### Watch Episode
- **Route**: `/watch/<eps_title>`
- **Method**: `GET`, `POST`
- Streams the selected episode and provides navigation options to go to the next or previous episode.

### Custom 404 Page
- **Route**: `/404`
- Displays a custom error message if the requested page is not found.

## Future Enhancements
- User authentication for tracking watched episodes.
- Commenting and rating system for anime episodes.
- Improved mobile responsiveness.

## License
This project is licensed under the MIT License.

## Contributing
Pull requests and issues are welcome. Please make sure to update tests as appropriate.

---

Thank you for visiting **Yume Animez**!