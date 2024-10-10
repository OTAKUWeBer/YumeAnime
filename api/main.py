from flask import Flask, render_template, request, session, redirect
import aiohttp
from bs4 import BeautifulSoup


app = Flask(__name__)

gogo_url = "https://www.anitaku.pe"

app.secret_key = 'W#b%052441%animez'

COOKIES = {
    '_ga_X2C65NWLE2': 'GS1.1.1718531678.3.0.1718531678.0.0.0',
    '_ga': 'GA1.1.251359287.1718516408',
    'gogoanime': '2stn8gti5vihjk80dnhgvh3s72',
    'auth': 'KhXMsD6IEey4qis2s%2F0Z4mnIjleMwfcORDZuXzqiXnhuF5Dnuq6iqNS4OrJ%2Bz1uqm1MJt%2BcgHZ0GKakQT1CapQ%3D%3D',
}

async def grab_id(url):
    """Grab the anime ID from the anime details page asynchronously."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response_content = await response.text()
            soup = BeautifulSoup(response_content, "html.parser")
            anime_id = soup.find("input", {"id": "movie_id"})["value"]
            return anime_id

async def home_page():
    results = {}
    url = f"{gogo_url}/home.html"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    anime_list = soup.find_all("ul", {"class": "items"})

    for ul in anime_list:
        items = ul.find_all("li")
        for item in items:
            title = item.find("a").get("title")
            link = item.find("a").get("href")
            anime_page = f"{gogo_url}{link}"

            # Fetch image for each anime
            image_url = item.find("img").get("src")
            results[title] = {"link": anime_page, "image_url": image_url}

    return results

    
    
async def search_anime_query(search):
    """Search for anime based on the user's query, including their images."""
    results = {}
    url = f"{gogo_url}/search.html?keyword={search}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    anime_list = soup.find_all("ul", {"class": "items"})

    for ul in anime_list:
        items = ul.find_all("li")
        for item in items:
            title = item.find("a").get("title")
            link = item.find("a").get("href")
            anime_page = f"{gogo_url}{link}"

            # Fetch image for each anime
            image_url = item.find("img").get("src")
            results[title] = {"link": anime_page, "image_url": image_url}

    return results


async def total_episodes(selected_link):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(selected_link) as detail_response:
                # Check if the request was successful
                detail_response.raise_for_status()  # Raise an error for bad responses
                detail_html = await detail_response.text()

        detail_soup = BeautifulSoup(detail_html, "html.parser")
        episode_page = detail_soup.find("ul", {"id": "episode_page"})
        
        if episode_page:
            last_episode = episode_page.find_all("li")[-1]
            total_episodes = int(last_episode.find("a")["ep_end"])  # Convert to integer
        else:
            total_episodes = 0
            
    except Exception:
        total_episodes = 0  # Set to 0 or handle the error as needed

    return total_episodes


async def fetch_episode_links(selected_link):
    """Fetch episode links for the selected anime."""
    ANIME_ID = await grab_id(selected_link)
    anime_eps_url = f"https://ajax.gogocdn.net/ajax/load-list-episode?ep_start=0&ep_end=1700&id={ANIME_ID}"

    episode_links = []
    async with aiohttp.ClientSession() as session:
        async with session.get(anime_eps_url) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                container = soup.find("ul", {"id": "episode_related"})
                if container:
                    for list_item in container.find_all("li"):
                        link = list_item.find("a")
                        if link:
                            episode_link = f"{gogo_url}{link['href'][1:]}"
                            episode_links.append(episode_link)
    return reversed(episode_links)


async def show_link(selected_link):
    """Fetch episode links for the selected anime."""
    ANIME_ID = await grab_id(selected_link)
    anime_eps_url = f"https://ajax.gogocdn.net/ajax/load-list-episode?ep_start=0&ep_end=1700&id={ANIME_ID}"

    episode_num = []
    async with aiohttp.ClientSession() as session:
        async with session.get(anime_eps_url) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                container = soup.find("ul", {"id": "episode_related"})
                if container:
                    for list_item in container.find_all("li"):
                        link = list_item.find("a")
                        if link and link['href']:
                            href = link['href']
                            # Extract the episode number by splitting the link (customize based on actual URL structure)
                            episode = href.split("-")[-1]  # Assuming episode number is at the end of the URL
                            episode_num.append(episode)
    return reversed(episode_num)


async def watch_link(episode_url):
    """Retrieve the episode download link for 1280x720 resolution."""
    async with aiohttp.ClientSession(cookies=COOKIES) as session:
        async with session.get(episode_url) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                container = soup.find("div", {"class": "cf-download"})
                if container:
                    links = container.find_all("a")
                    download_link = None

                    # Find the download link for 1280x720 resolution
                    for link in links:
                        if "1280x720" in link.text:
                            download_link = link['href']
                            break  # Exit once we find the desired resolution
                        else:
                            download_link = link['href']
                            

                    return download_link if download_link else None
                else:
                    return None  # Return None if the container is not found
            else:
                return None  # Return None if the request fails


@app.route('/', methods=["GET"])
async def index():
    return redirect ("/home")


@app.route('/home', methods=["GET"])
async def home():
    suggestions = await home_page() 
    return render_template('index.html', suggestions=suggestions)


@app.route('/search', methods=['GET'])
async def search():
    """Handle the search request and display results."""
    search_query = request.args.get('search')
    if not search_query:
        return render_template('index.html', error="Please enter an anime name.")

    results = await search_anime_query(search_query)

    if not results:
        return render_template('index.html', error="No results found.")

    return render_template('results.html', query=search_query, results=results)

@app.route('/episodes', methods=['POST'])
async def episodes():
    """Display episodes for the selected anime."""
    selected_link = request.form.get('selected_link')
    episode_links = await fetch_episode_links(selected_link)
    episode_nums = await show_link(selected_link)

    # Fetch the total number of episodes
    total_eps = await total_episodes(selected_link)
    
    # Store total episodes in session
    session['total_episodes'] = total_eps

    # Zip episode_links and episode_nums together
    episodes = zip(episode_links, episode_nums)
    
    return render_template('episodes.html', episodes=episodes, total_episodes=total_eps)




@app.route('/watch', methods=['POST'])
async def watch():
    """Render the watch page for the selected episode."""
    episode_url = request.form.get('episode_url')  # Get episode URL from the form
    episode_link = await watch_link(episode_url)  # Retrieve the video link

    # Extract current episode number
    current_episode = int(episode_url.split("-")[-1])  # Assuming the URL contains the episode number at the end

    # Get total episodes from the session
    total_episodes = session.get('total_episodes', 0)  # Get total episodes from the session

    # Previous and Next episode numbers
    prev_episode_number = current_episode - 1 if current_episode > 1 else None
    next_episode_number = current_episode + 1 if current_episode < total_episodes else None

    # Generate previous and next episode URLs
    prev_episode_url = episode_url.replace(f"-{current_episode}", f"-{prev_episode_number}") if prev_episode_number else None
    next_episode_url = episode_url.replace(f"-{current_episode}", f"-{next_episode_number}") if next_episode_number else None

    return render_template('watch.html',
                           episode_link=episode_link,
                           prev_episode_url=prev_episode_url,
                           next_episode_url=next_episode_url,
                           prev_episode_number=prev_episode_number,
                           next_episode_number=next_episode_number)





if __name__ == '__main__':
    app.run(debug=True)
