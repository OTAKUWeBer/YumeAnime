import aiohttp
from bs4 import BeautifulSoup

class GogoAnimeScraper:
    
    gogo_url = "https://gogoanime3.cc"
    def __init__(self):
        self.base_url = self.gogo_url
        self.cookies = {
            '_ga_X2C65NWLE2': 'GS1.1.1718531678.3.0.1718531678.0.0.0',
            '_ga': 'GA1.1.251359287.1718516408',
            'gogoanime': '2stn8gti5vihjk80dnhgvh3s72',
            'auth': 'KhXMsD6IEey4qis2s%2F0Z4mnIjleMwfcORDZuXzqiXnhuF5Dnuq6iqNS4OrJ%2Bz1uqm1MJt%2BcgHZ0GKakQT1CapQ%3D%3D',
        }

    async def fetch_page(self, url):
        """Helper function to fetch page content."""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                return None

    async def grab_id(self, url):
        """Grab the anime ID from the anime details page asynchronously."""
        try:
            page_content = await self.fetch_page(url)
            if page_content:
                soup = BeautifulSoup(page_content, "html.parser")
                movie_id_input = soup.find("input", {"id": "movie_id"})
                if movie_id_input:
                    return movie_id_input.get("value")
            return None
        except Exception as e:
            raise ValueError(f"Error fetching anime ID: {e}")

    async def fetch_anime_page(self, endpoint: str):
        """Fetch an anime page and scrape titles and images."""
        try:
            html = await self.fetch_page(f"{self.base_url}{endpoint}")
            if not html:
                return {}

            soup = BeautifulSoup(html, "html.parser")
            anime_list = soup.find_all("ul", {"class": "items"})
            results = {}
            for ul in anime_list:
                for item in ul.find_all("li"):
                    title = item.find("a").get("title", "No Title")
                    link = f"{self.base_url}{item.find('a').get('href', '')}"
                    image_url = item.find("img").get("src", "default_image.png")
                    results[title] = {"link": link, "image_url": image_url}
            return results
        except Exception as e:
            print(f"Error in fetch_anime_page({endpoint}): {e}")
            return {}

    async def home_page(self):
        """Fetch the home page anime titles and images."""
        return await self.fetch_anime_page("")

    async def new_season(self):
        """Fetch the new season anime titles and images."""
        return await self.fetch_anime_page("/new-season.html")

    async def movies_page(self):
        """Fetch the anime movies titles and images."""
        return await self.fetch_anime_page("/anime-movies.html")

    async def trending(self):
        """Fetch the trending anime titles and images."""
        return await self.fetch_anime_page("/popular.html")


    async def search_anime_query(self, search):
        """Search for anime based on the user's query."""
        try:
            url = f"{self.base_url}/search.html?keyword={search}"
            html = await self.fetch_page(url)
            if not html:
                return {}

            soup = BeautifulSoup(html, "html.parser")
            anime_list = soup.find_all("ul", {"class": "items"})
            results = {}
            for ul in anime_list:
                for item in ul.find_all("li"):
                    title = item.find("a").get("title", "No Title")
                    link = f"{self.base_url}{item.find('a').get('href', '')}"
                    image_url = item.find("img").get("src", "default_image.png")
                    results[title] = {"link": link, "image_url": image_url}
            return results
        except Exception as e:
            print(f"Error in search_anime_query: {e}")
            return {}

    async def get_title(self, search):
        """Fetch the title of an anime based on its page URL."""
        try:
            html = await self.fetch_page(search)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                title_tag = soup.find('h1')
                return title_tag.text.strip() if title_tag else "Title not found"
            return "Page not found"
        except Exception as e:
            print(f"Error in get_title: {e}")
            return "Error fetching title"

    async def fetch_anime_status(self, selected_link):
        """Fetch the status (airing or completed) of an anime."""
        try:
            html = await self.fetch_page(selected_link)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                anime_info_body = soup.find("div", {"class": "anime_info_body"})
                if anime_info_body:
                    for p in anime_info_body.find_all("p", {"class": "type"}):
                        if "Status:" in p.text:
                            return p.text.replace("Status:", "").strip()
            return "Status not found"
        except Exception as e:
            print(f"Error in fetch_anime_status: {e}")
            return "Error fetching status"

    async def fetch_anime_genres(self, selected_link):
        try:
            html = await self.fetch_page(selected_link)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                anime_info_body = soup.find("div", {"class": "anime_info_body"})
                if anime_info_body:
                    for p in anime_info_body.find_all("p", {"class": "type"}):
                        span_tag = p.find("span")
                        if span_tag and "Genre:" in span_tag.text:
                            # Extract all <a> tags within the <p> element
                            genres = [a.text.strip(", ") for a in p.find_all("a")]
                            return ", ".join(genres)  # Join genres into a single string
            return "Genres not found"
        except Exception as e:
            print(f"Error in fetch_anime_genres: {e}")
            return "Error fetching genre"

    async def total_episodes(self, selected_link):
        """Fetch the total number of episodes of an anime."""
        try:
            html = await self.fetch_page(selected_link)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                episode_page = soup.find("ul", {"id": "episode_page"})
                if episode_page:
                    last_episode = episode_page.find_all("li")[-1]
                    return int(last_episode.find("a").get("ep_end", 0))
            return 0
        except Exception as e:
            print(f"Error in total_episodes: {e}")
            return 0

    async def fetch_episode_links(self, selected_link):
        """Fetch all episode links for a specific anime."""
        try:
            anime_id = await self.grab_id(selected_link)
            end_episode = await self.total_episodes(selected_link)
            anime_eps_url = f"https://ajax.gogocdn.net/ajax/load-list-episode?ep_start=0&ep_end={end_episode}&id={anime_id}"
            html = await self.fetch_page(anime_eps_url)
            episode_links = []

            if html:
                soup = BeautifulSoup(html, "html.parser")
                container = soup.find("ul", {"id": "episode_related"})
                for list_item in container.find_all("li"):
                    link = list_item.find("a")
                    if link:
                        episode_links.append(f"{self.base_url}{link['href'][1:]}")
            return list(reversed(episode_links))
        except Exception as e:
            print(f"Error in fetch_episode_links: {e}")
            return []

    async def show_episode_number(self, selected_link):
        """Fetch episode numbers for a specific anime."""
        try:
            anime_id = await self.grab_id(selected_link)
            end_episode = await self.total_episodes(selected_link)
            anime_eps_url = f"https://ajax.gogocdn.net/ajax/load-list-episode?ep_start=0&ep_end={end_episode}&id={anime_id}"
            html = await self.fetch_page(anime_eps_url)
            episode_num = []

            if html:
                soup = BeautifulSoup(html, "html.parser")
                container = soup.find("ul", {"id": "episode_related"})
                for list_item in container.find_all("li"):
                    link = list_item.find("a")
                    if link and link['href']:
                        href = link['href']

                        # Check if there's no episode number after the anime name
                        if 'episode-' not in href:
                            episode_num.append('0')
                        else:
                            # Extract the episode number
                            episode = href.split("episode-")[-1]

                            # Convert "12-5" to "12.5"
                            if '-' in episode:
                                episode = episode.replace('-', '.')

                            episode_num.append(episode)

            return list(reversed(episode_num))
        except Exception as e:
            print(f"Error in show_eps: {e}")
            return []


    async def video_link(self, episode_url):
        """Fetch the download link for 1280x720 resolution."""
        try:
            async with aiohttp.ClientSession(cookies=self.cookies) as session:
                async with session.get(episode_url) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, "html.parser")
                        container = soup.find("div", {"class": "cf-download"})
                        if container:
                            for link in container.find_all("a"):
                                if "1280x720" in link.text:
                                    return link['href']
                            links = container.find_all("a")
                            if links:
                                return links[-1]['href'] # use the highest resulation if 720p not found
            return None
        except Exception as e:
            print(f"Error in video_link: {e}")
            return None
