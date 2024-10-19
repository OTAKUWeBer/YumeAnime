from flask import Flask, render_template, request, session, redirect
import re
from .scrapers import GogoAnimeScraper



app = Flask(__name__)
app.secret_key = 'W#b%052441%animez'

GS = GogoAnimeScraper()

@app.route('/', methods=["GET"])
async def index():
    return redirect("/home")


@app.route('/home', methods=["GET"])
async def home():
    """Fetch anime suggestions for the home page."""
    try:
        suggestions = await GS.home_page()
        return render_template('index.html', suggestions=suggestions)
    except Exception as e:
        return render_template('index.html', error=f"Error fetching home page data: {e}")


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
        episode_number = await GS.show_episode_number(selected_link)
        total_episodes = await GS.total_episodes(selected_link)

        # Store total episodes in session
        session['total_episodes'] = total_episodes

        # Zip episode_links and episode_nums together
        episodes = zip(episode_links, episode_number)

        return render_template('episodes.html', episodes=episodes, total_episodes=total_episodes, title=title, status=status)

    except Exception as e:
        return render_template('index.html', error=f"Error fetching episodes: {e}")


@app.route('/watch/<eps_title>', methods=['GET', 'POST'])
async def watch(eps_title):
    """Render the watch page for the episode."""
    try:
        # Construct the episode URL
        episode_url = f"{GS.gogo_url}/{eps_title}"
        
        # Extract the base anime title (for 'back to episodes' link)
        back_to_ep = re.split(r'-episode-\d+', eps_title)[0]

        # Retrieve the video link
        watch_link = await GS.watch_link(episode_url)

        # Extract episode number
        episode_match = re.search(r'-episode-(\d+)$', episode_url)
        if not episode_match:
            return render_template('404.html', error_message="Invalid episode URL format.")

        current_episode = int(episode_match.group(1))  # Get the episode number

        # Get total episodes from the session
        total_episodes = await GS.total_episodes(episode_url)

        # Calculate previous and next episode numbers
        prev_episode_number = current_episode - 1 if current_episode > 1 else None
        next_episode_number = current_episode + 1 if current_episode < total_episodes else None

        # Generate previous and next episode URLs
        prev_episode_url = re.sub(r'-episode-(\d+)$', f'-episode-{prev_episode_number}', episode_url) if prev_episode_number else None
        next_episode_url = re.sub(r'-episode-(\d+)$', f'-episode-{next_episode_number}', episode_url) if next_episode_number else None

        return render_template('watch.html',
                               back_to_ep=back_to_ep,
                               watch_link=watch_link,
                               Episode=current_episode,
                               prev_episode_url=prev_episode_url,
                               next_episode_url=next_episode_url,
                               prev_episode_number=prev_episode_number,
                               next_episode_number=next_episode_number)
    except Exception as e:
        return render_template('404.html', error_message="An error occurred while fetching the episode.")

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)