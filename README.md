# Yume Anime

**Yume Anime** is a Python-based web application built using Flask that allows users to search, browse, and stream anime episodes. It scrapes data from the **GogoAnime** website, providing users with an intuitive interface to explore anime series, view available episodes, and watch them directly within the app.

## Website URL
- Live Site: [YumeAnime](https://yume-animez.vercel.app/home)

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
- Improved mobile responsiveness.

## License
This project is licensed under the MIT License.

## Contributing
Pull requests and issues are welcome. Please make sure to update tests as appropriate.

---

Thank you for visiting **Yume Animez**!
