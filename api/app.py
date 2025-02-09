from flask import Flask, render_template, request, redirect, url_for, session, flash
import re
from markupsafe import escape
from dotenv import load_dotenv
import os
from .scrapers import GogoAnimeScraper
from .utils import create_user, get_user, user_exists

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_KEY")

GS = GogoAnimeScraper()

@app.before_request
def redirect_to_urgent():
    # Define the paths that should be redirected
    redirect_paths = ['/home', '/search', '/movies', '/trending', '/new-seasons','/login', '/signup', '/profile']
    if request.path in redirect_paths:
        return redirect("/urgent-announcement")

@app.route('/', methods=["GET"])
async def index():
    return redirect("/home")


@app.route('/home', methods=["GET"])
async def home():
    """Fetch anime suggestions for the home page."""
    info = "Latest Episodes"
    try:
        suggestions = await GS.home_page()
        return render_template('index.html', suggestions=suggestions, info=info)
    except Exception as e:
        return render_template('index.html', error=f"Error fetching home page data: {e}", info=info)
  
    
@app.route('/new-seasons', methods=["GET"])
async def new_season():
    """Fetch anime suggestions for the home page."""
    info = "Latest Seasons"
    try:
        suggestions = await GS.new_season()
        return render_template('index.html', suggestions=suggestions, info=info)
    except Exception as e:
        return render_template('index.html', error=f"Error fetching home page data: {e}", info=info)
 
 
@app.route('/movies', methods=["GET"])
async def movies():
    """Fetch anime suggestions for the home page."""
    info = "Latest Movies"
    try:
        suggestions = await GS.movies_page()
        return render_template('index.html', suggestions=suggestions, info=info)
    except Exception as e:
        return render_template('index.html', error=f"Error fetching home page data: {e}", info=info)   
    
    
@app.route('/trending', methods=["GET"])
async def trending_anime():
    """Fetch anime suggestions for the home page."""
    info = "Popular Animes"
    try:
        suggestions = await GS.trending()
        return render_template('index.html', suggestions=suggestions, info=info)
    except Exception as e:
        return render_template('index.html', error=f"Error fetching home page data: {e}", info=info)    


@app.route('/search', methods=['GET'])
async def search():
    """Handle the search request and display results."""
    search_query = request.args.get('q')
    if not search_query:
        return render_template('index.html', error="Please enter an anime name.")

    try:
        results = await GS.search_anime_query(search_query)
        if not results:
            return render_template('index.html', error="No results found.")

        return render_template('results.html', query=search_query, results=results)
    except Exception as e:
        return render_template('index.html', error=f"Error fetching search results: {e}")


@app.route('/episodes/<anime_title>', methods=['GET'])
async def episodes(anime_title):
    """Fetch and display episodes for the selected anime."""
    try:
        # Reconstruct the selected link from the title
        selected_link = f"{GS.gogo_url}/category/{anime_title}"

        # Fetch the title, episode links, status, and total episodes
        title = await GS.get_title(selected_link)
        episode_links = await GS.fetch_episode_links(selected_link)
        status = await GS.fetch_anime_status(selected_link)
        genre = await GS.fetch_anime_genres(selected_link)
        episode_number = await GS.show_episode_number(selected_link)
        total_episodes = await GS.total_episodes(selected_link)

        # Zip episode_links and episode_nums together
        episodes = zip(episode_links, episode_number)

        return render_template('episodes.html', episodes=episodes, total_episodes=total_episodes, title=title, status=status, genre=genre)

    except Exception as e:
        return render_template('index.html', error=f"Error fetching episodes: {e}")


@app.route('/watch/<eps_title>', methods=['GET', 'POST'])
async def watch(eps_title):
    """Render the watch page for the episode or series/season."""
    try:
        # Construct the episode URL
        episode_url = f"{GS.gogo_url}/{escape(eps_title)}"
        
        # Check if the URL contains an episode pattern (e.g., `-episode-X`)
        episode_match = re.search(r'-episode-(\d+([.-]\d+)?)$', eps_title)

        if episode_match:
            # It's an episode URL, handle episode-specific logic
            current_episode = episode_match.group(1)  # e.g., '1', '13-5', etc.

            # Extract the base anime title (for 'back to episodes' link)
            back_to_ep = re.split(r'-episode-\d+([.-]\d+)?$', eps_title)[0]

            # Retrieve the video link
            video_link = await GS.video_link(episode_url)

            # Get total episodes from the session, excluding special episodes like 0, 13-5, etc.
            total_episodes = await GS.total_episodes(episode_url)

            # Handle next and previous episode logic (only for integer episodes)
            if re.match(r'^\d+$', current_episode):  # Regular integer episode
                current_episode_number = int(current_episode)

                # Calculate previous and next episode numbers
                prev_episode_number = current_episode_number - 1 if current_episode_number > 1 else None
                next_episode_number = current_episode_number + 1 if current_episode_number < total_episodes else None

                # Generate previous and next episode URLs
                prev_episode_url = re.sub(r'-episode-\d+$', f'-episode-{prev_episode_number}', eps_title) if prev_episode_number else None
                next_episode_url = re.sub(r'-episode-\d+$', f'-episode-{next_episode_number}', eps_title) if next_episode_number else None
            else:
                # For special episodes (like 13-5, 0, etc.), no next/previous buttons
                prev_episode_number = None
                next_episode_number = None
                prev_episode_url = None
                next_episode_url = None

        else:
            # If no episode pattern is found, treat it as an episode without navigation (e.g., `kimi-ni-todoke-3rd-season`)
            current_episode = None
            back_to_ep = eps_title  # Keep the full title for back navigation
            video_link = await GS.video_link(episode_url)
            
            # No next/previous for season-like URLs
            prev_episode_url = None
            next_episode_url = None
            prev_episode_number = None
            next_episode_number = None

        return render_template('watch.html',
                               back_to_ep=back_to_ep,
                               video_link=video_link,
                               Episode=current_episode if current_episode else "Special",
                               prev_episode_url=prev_episode_url,
                               next_episode_url=next_episode_url,
                               prev_episode_number=prev_episode_number,
                               next_episode_number=next_episode_number,
                               eps_title=eps_title)
    except Exception as e:
        return render_template('404.html', error_message="An error occurred while fetching the episode.")


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Check if the username already exists
        if user_exists(username):
            flash('Username already exists!')
            return redirect(url_for('signup'))
        
        # Enforce password length requirement
        if len(password) < 6:
            flash('Password must be at least 6 characters long.')
            return redirect(url_for('signup'))
        
        # Create the user if validations pass
        create_user(username, password)
        flash('Signup successful! You can now log in.')
        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = get_user(username, password)
        
        if user:
            session['username'] = username
            session['_id'] = user['_id']
            flash('Login successful!')
            return redirect(url_for('profile'))
        else:
            flash('Invalid username or password.')
    
    return render_template('login.html')

@app.route('/profile')
def profile():
    if 'username' in session:
        username = session['username']
        user_id = session['_id']
        user = "hold"
        return render_template('profile.html', username=username, user_id=user_id, user=user)
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('_id', None)
    flash('You have been logged out.')
    return redirect(url_for('home'))

@app.errorhandler(404)
def page_not_found(e):
    """Redirect 404 errors to urgent-announcement."""
    return redirect("/urgent-announcement")

@app.errorhandler(500)
def internal_server_error(e):
    """Redirect 500 errors to urgent-announcement."""
    return redirect("/urgent-announcement")

@app.route("/urgent-announcement")
def urgent_announcement():
    return render_template("urgent-announcement.html")

if __name__ == '__main__':
    app.run(debug=True)