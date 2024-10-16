from flask import Flask, render_template, request, session, redirect
import re
from scrapes import *



app = Flask(__name__)

app.secret_key = 'W#b%052441%animez'

@app.route('/', methods=["GET"])
async def index():
    return redirect("/home")


@app.route('/home', methods=["GET"])
async def home():
    suggestions = await home_page()
    return render_template('index.html', suggestions=suggestions)


@app.route('/search', methods=['GET'])
async def search():
    """Handle the search request and display results."""
    search_query = request.args.get('q')
    if not search_query:
        return render_template('index.html', error="Please enter an anime name.")

    results = await search_anime_query(search_query)

    if not results:
        return render_template('index.html', error="No results found.")

    return render_template('results.html', query=search_query, results=results)


# Use dynamic route for episodes based on anime title
@app.route('/episodes/<anime_title>', methods=['GET'])
async def episodes(anime_title):
    """Fetch and display episodes for the selected anime."""
    # Reconstruct the selected link from the title
    selected_link = f"https://anitaku.pe/category/{anime_title}"
    
    # Fetch the title of the selected anime
    title = await get_title(selected_link)
    
    # Fetch episode links based on the title
    episode_links = await fetch_episode_links(selected_link)
    
    # Status of anime
    status = await fetch_anime_status(selected_link)
    
    # Fetch the episode numbers if needed
    episode_nums = await show_eps(selected_link)
    
    # Get total episodes
    total_eps = await total_episodes(selected_link)
    
    # Store total episodes in session
    session['total_episodes'] = total_eps
    
    # Zip episode_links and episode_nums together
    episodes = zip(episode_links, episode_nums)
    
    return render_template('episodes.html', episodes=episodes, total_episodes=total_eps, title=title, status=status)


@app.route('/watch/<eps_title>', methods=['GET', 'POST'])
async def watch(eps_title):
    """Render the watch page for the episode."""
    episode_url = f"{gogo_url}/{eps_title}"
    
    back_to_ep = episode_url.split('/')[-1]
    back_to_ep = back_to_ep.split('-episode')[0]

    # Retrieve the video link
    episode_link = await watch_link(episode_url)


    episode_match = re.search(r'-episode-(\d+)$', episode_url)
    if not episode_match:
        # Handle case where episode number is not found
        return "Invalid episode URL format."

    current_episode = int(episode_match.group(1))  # Get the episode number

    # Get total episodes from the session
    total_episodes = session.get('total_episodes', 0)  # Get total episodes from the session

    # Previous and Next episode numbers
    prev_episode_number = current_episode - 1 if current_episode > 1 else None
    next_episode_number = current_episode + 1 if current_episode < total_episodes else None

    # Generate previous and next episode URLs, replacing only the episode number part
    prev_episode_url = re.sub(r'-episode-(\d+)$', f'-episode-{prev_episode_number}', episode_url) if prev_episode_number else None
    next_episode_url = re.sub(r'-episode-(\d+)$', f'-episode-{next_episode_number}', episode_url) if next_episode_number else None

    return render_template('watch.html',
                           back_to_ep=back_to_ep,
                           episode_link=episode_link,
                           Episode=current_episode,
                           prev_episode_url=prev_episode_url,
                           next_episode_url=next_episode_url,
                           prev_episode_number=prev_episode_number,
                           next_episode_number=next_episode_number)



if __name__ == '__main__':
    app.run(debug=True)