"""Platform registry for username presence detection.

Curated database of platforms with not-found indicators and category metadata.
Designed for multi-factor confidence scoring — HTTP status alone is insufficient
for many platforms that return 200 even for missing profiles.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlatformEntry:
    """Metadata for a single platform in the username presence registry."""

    name: str
    url_template: str  # Must contain {username}
    category: str  # social | developer | gaming | creative | professional | forum | finance
    # Strings that appear in the response body of a *missing* profile page
    not_found_indicators: tuple[str, ...] = field(default_factory=tuple)
    # Strings that confirm a *real* profile page
    found_indicators: tuple[str, ...] = field(default_factory=tuple)
    # How reliable HTTP 200 is for this platform (1.0 = perfect, 0.5 = unreliable)
    confidence_weight: float = 0.8
    # Whether this platform requires a GET (not HEAD) to read content
    requires_body: bool = True


PLATFORM_REGISTRY: dict[str, PlatformEntry] = {
    # ── Social / General ───────────────────────────────────────────────────────
    "GitHub": PlatformEntry(
        name="GitHub",
        url_template="https://github.com/{username}",
        category="developer",
        not_found_indicators=("Not Found", "This is not the web page you are looking for"),
        found_indicators=("repositories", "followers", "following"),
        confidence_weight=0.95,
    ),
    "Twitter": PlatformEntry(
        name="Twitter",
        url_template="https://twitter.com/{username}",
        category="social",
        not_found_indicators=("This account doesn\u2019t exist", "Hmm...this page doesn\u2019t exist"),
        found_indicators=(),
        confidence_weight=0.75,
    ),
    "Reddit": PlatformEntry(
        name="Reddit",
        url_template="https://www.reddit.com/user/{username}",
        category="forum",
        not_found_indicators=("Sorry, nobody on Reddit goes by that name", "page not found"),
        found_indicators=("karma", "cake day"),
        confidence_weight=0.95,
    ),
    "Instagram": PlatformEntry(
        name="Instagram",
        url_template="https://www.instagram.com/{username}/",
        category="social",
        not_found_indicators=("Sorry, this page isn\u2019t available"),
        found_indicators=(),
        confidence_weight=0.8,
    ),
    "TikTok": PlatformEntry(
        name="TikTok",
        url_template="https://www.tiktok.com/@{username}",
        category="social",
        not_found_indicators=("Couldn\u2019t find this account"),
        found_indicators=(),
        confidence_weight=0.7,
    ),
    "YouTube": PlatformEntry(
        name="YouTube",
        url_template="https://www.youtube.com/@{username}",
        category="social",
        not_found_indicators=("This page isn\u2019t available"),
        found_indicators=("subscribers",),
        confidence_weight=0.8,
    ),
    "Pinterest": PlatformEntry(
        name="Pinterest",
        url_template="https://www.pinterest.com/{username}/",
        category="creative",
        not_found_indicators=("Hmm\u2026 that page doesn\u2019t exist"),
        found_indicators=("Pins", "Followers"),
        confidence_weight=0.85,
    ),
    "Tumblr": PlatformEntry(
        name="Tumblr",
        url_template="https://{username}.tumblr.com/",
        category="social",
        not_found_indicators=("There\u2019s nothing here.", "404"),
        found_indicators=(),
        confidence_weight=0.75,
    ),
    "Medium": PlatformEntry(
        name="Medium",
        url_template="https://medium.com/@{username}",
        category="professional",
        not_found_indicators=("Page not found"),
        found_indicators=("followers", "Following"),
        confidence_weight=0.85,
    ),
    "Snapchat": PlatformEntry(
        name="Snapchat",
        url_template="https://www.snapchat.com/add/{username}",
        category="social",
        not_found_indicators=(),
        found_indicators=("Add me on Snapchat",),
        confidence_weight=0.9,
    ),
    # ── Developer Platforms ────────────────────────────────────────────────────
    "GitLab": PlatformEntry(
        name="GitLab",
        url_template="https://gitlab.com/{username}",
        category="developer",
        not_found_indicators=("The page you\u2019re looking for could not be found"),
        found_indicators=("Overview", "Activity", "Groups"),
        confidence_weight=0.9,
    ),
    "Bitbucket": PlatformEntry(
        name="Bitbucket",
        url_template="https://bitbucket.org/{username}/",
        category="developer",
        not_found_indicators=("Sorry, we can\u2019t find that page"),
        found_indicators=(),
        confidence_weight=0.85,
    ),
    "Keybase": PlatformEntry(
        name="Keybase",
        url_template="https://keybase.io/{username}",
        category="developer",
        not_found_indicators=("Not a Keybase user"),
        found_indicators=("Keybase proof", "on keybase"),
        confidence_weight=0.95,
    ),
    "HackerNews": PlatformEntry(
        name="HackerNews",
        url_template="https://news.ycombinator.com/user?id={username}",
        category="forum",
        not_found_indicators=("No such user."),
        found_indicators=("karma",),
        confidence_weight=0.98,
    ),
    "StackOverflow": PlatformEntry(
        name="StackOverflow",
        url_template="https://stackoverflow.com/users/{username}",
        category="developer",
        not_found_indicators=("Page Not Found"),
        found_indicators=("reputation", "badges"),
        confidence_weight=0.7,  # URL uses numeric IDs, username may be slug
    ),
    "Dev.to": PlatformEntry(
        name="Dev.to",
        url_template="https://dev.to/{username}",
        category="developer",
        not_found_indicators=("404", "Route not found"),
        found_indicators=("posts", "comments"),
        confidence_weight=0.9,
    ),
    "Replit": PlatformEntry(
        name="Replit",
        url_template="https://replit.com/@{username}",
        category="developer",
        not_found_indicators=("Page not found"),
        found_indicators=("Repls", "followers"),
        confidence_weight=0.9,
    ),
    "Codepen": PlatformEntry(
        name="Codepen",
        url_template="https://codepen.io/{username}",
        category="developer",
        not_found_indicators=("The pen you are looking for could not be found", "Hmm"),
        found_indicators=("Pens", "followers"),
        confidence_weight=0.85,
    ),
    "npm": PlatformEntry(
        name="npm",
        url_template="https://www.npmjs.com/~{username}",
        category="developer",
        not_found_indicators=("Not found", "User not found"),
        found_indicators=("packages",),
        confidence_weight=0.9,
    ),
    "PyPI": PlatformEntry(
        name="PyPI",
        url_template="https://pypi.org/user/{username}/",
        category="developer",
        not_found_indicators=("404", "Not Found"),
        found_indicators=("projects",),
        confidence_weight=0.95,
    ),
    "DockerHub": PlatformEntry(
        name="DockerHub",
        url_template="https://hub.docker.com/u/{username}/",
        category="developer",
        not_found_indicators=("404", "Page not found"),
        found_indicators=("repositories",),
        confidence_weight=0.9,
    ),
    "HackerRank": PlatformEntry(
        name="HackerRank",
        url_template="https://www.hackerrank.com/{username}",
        category="developer",
        not_found_indicators=("Uh oh! Something went wrong", "page not found"),
        found_indicators=("Badges", "Certificates"),
        confidence_weight=0.85,
    ),
    "LeetCode": PlatformEntry(
        name="LeetCode",
        url_template="https://leetcode.com/{username}/",
        category="developer",
        not_found_indicators=("does not exist"),
        found_indicators=("problems solved", "contest rating"),
        confidence_weight=0.9,
    ),
    "Kaggle": PlatformEntry(
        name="Kaggle",
        url_template="https://www.kaggle.com/{username}",
        category="developer",
        not_found_indicators=("404", "We could not find"),
        found_indicators=("competitions", "notebooks"),
        confidence_weight=0.85,
    ),
    # ── Creative Platforms ─────────────────────────────────────────────────────
    "Behance": PlatformEntry(
        name="Behance",
        url_template="https://www.behance.net/{username}",
        category="creative",
        not_found_indicators=("This URL doesn\u2019t exist", "Page Not Found"),
        found_indicators=("Projects", "Appreciations"),
        confidence_weight=0.9,
    ),
    "Dribbble": PlatformEntry(
        name="Dribbble",
        url_template="https://dribbble.com/{username}",
        category="creative",
        not_found_indicators=("Whoops, that page is gone", "404"),
        found_indicators=("shots", "followers"),
        confidence_weight=0.9,
    ),
    "Flickr": PlatformEntry(
        name="Flickr",
        url_template="https://www.flickr.com/people/{username}/",
        category="creative",
        not_found_indicators=("Oops! We can't find that page"),
        found_indicators=("photos", "albums"),
        confidence_weight=0.85,
    ),
    "Vimeo": PlatformEntry(
        name="Vimeo",
        url_template="https://vimeo.com/{username}",
        category="creative",
        not_found_indicators=("Sorry, we couldn\u2019t find that page"),
        found_indicators=("videos", "followers"),
        confidence_weight=0.85,
    ),
    "SoundCloud": PlatformEntry(
        name="SoundCloud",
        url_template="https://soundcloud.com/{username}",
        category="creative",
        not_found_indicators=("We can\u2019t find that user", "404"),
        found_indicators=("followers", "tracks"),
        confidence_weight=0.9,
    ),
    # ── Gaming Platforms ───────────────────────────────────────────────────────
    "Steam": PlatformEntry(
        name="Steam",
        url_template="https://steamcommunity.com/id/{username}",
        category="gaming",
        not_found_indicators=("The specified profile could not be found", "Error"),
        found_indicators=("Steam Level",),
        confidence_weight=0.9,
    ),
    "Twitch": PlatformEntry(
        name="Twitch",
        url_template="https://www.twitch.tv/{username}",
        category="gaming",
        not_found_indicators=("Sorry. Unless you\u2019ve got a time machine",),
        found_indicators=("followers",),
        confidence_weight=0.85,
    ),
    "Chess.com": PlatformEntry(
        name="Chess.com",
        url_template="https://www.chess.com/member/{username}",
        category="gaming",
        not_found_indicators=("Oops! That page doesn\u2019t exist",),
        found_indicators=("Games", "Rating"),
        confidence_weight=0.95,
    ),
    # ── Professional Platforms ─────────────────────────────────────────────────
    "ProductHunt": PlatformEntry(
        name="ProductHunt",
        url_template="https://www.producthunt.com/@{username}",
        category="professional",
        not_found_indicators=("Page not found",),
        found_indicators=("followers", "upvotes"),
        confidence_weight=0.85,
    ),
    "AngelList": PlatformEntry(
        name="AngelList",
        url_template="https://angel.co/{username}",
        category="professional",
        not_found_indicators=("Page not found", "404"),
        found_indicators=(),
        confidence_weight=0.75,
    ),
    "About.me": PlatformEntry(
        name="About.me",
        url_template="https://about.me/{username}",
        category="professional",
        not_found_indicators=("The page you are looking for doesn\u2019t exist", "404"),
        found_indicators=(),
        confidence_weight=0.9,
    ),
    # ── Forums / Communities ───────────────────────────────────────────────────
    "Quora": PlatformEntry(
        name="Quora",
        url_template="https://www.quora.com/profile/{username}",
        category="forum",
        not_found_indicators=("This page may have been removed",),
        found_indicators=("answers", "followers"),
        confidence_weight=0.8,
    ),
    "Goodreads": PlatformEntry(
        name="Goodreads",
        url_template="https://www.goodreads.com/{username}",
        category="forum",
        not_found_indicators=("Page not found",),
        found_indicators=("books", "friends"),
        confidence_weight=0.8,
    ),
    "Mastodon": PlatformEntry(
        name="Mastodon",
        url_template="https://mastodon.social/@{username}",
        category="social",
        not_found_indicators=("The page you are looking for isn\u2019t here",),
        found_indicators=("followers", "following"),
        confidence_weight=0.85,
    ),
    # ── Music Platforms ────────────────────────────────────────────────────────
    "Last.fm": PlatformEntry(
        name="Last.fm",
        url_template="https://www.last.fm/user/{username}",
        category="creative",
        not_found_indicators=("User not found",),
        found_indicators=("scrobbles", "Loved Tracks"),
        confidence_weight=0.95,
    ),
    "Spotify": PlatformEntry(
        name="Spotify",
        url_template="https://open.spotify.com/user/{username}",
        category="creative",
        not_found_indicators=("Page not found",),
        found_indicators=(),
        confidence_weight=0.7,
    ),
    # ── Misc ───────────────────────────────────────────────────────────────────
    "Pastebin": PlatformEntry(
        name="Pastebin",
        url_template="https://pastebin.com/u/{username}",
        category="misc",
        not_found_indicators=("Not Found (#404)",),
        found_indicators=("Public Pastes",),
        confidence_weight=0.9,
    ),
    "Gravatar": PlatformEntry(
        name="Gravatar",
        url_template="https://en.gravatar.com/{username}",
        category="misc",
        not_found_indicators=("Not Found",),
        found_indicators=("Profile",),
        confidence_weight=0.9,
    ),
    "Duolingo": PlatformEntry(
        name="Duolingo",
        url_template="https://www.duolingo.com/profile/{username}",
        category="misc",
        not_found_indicators=("We cannot find this user",),
        found_indicators=("streak", "XP"),
        confidence_weight=0.9,
    ),
    "Strava": PlatformEntry(
        name="Strava",
        url_template="https://www.strava.com/athletes/{username}",
        category="misc",
        not_found_indicators=("Oops!", "athlete could not be found"),
        found_indicators=("Activities", "followers"),
        confidence_weight=0.7,  # Uses numeric IDs
    ),
    "Telegram": PlatformEntry(
        name="Telegram",
        url_template="https://t.me/{username}",
        category="social",
        not_found_indicators=(),
        found_indicators=("If you have Telegram",),
        confidence_weight=0.85,
    ),
    "Codecademy": PlatformEntry(
        name="Codecademy",
        url_template="https://www.codecademy.com/profiles/{username}",
        category="developer",
        not_found_indicators=("404",),
        found_indicators=("courses", "streak"),
        confidence_weight=0.85,
    ),
}

# Lookup helpers
CATEGORIES = frozenset(p.category for p in PLATFORM_REGISTRY.values())


def get_by_category(category: str) -> dict[str, PlatformEntry]:
    return {k: v for k, v in PLATFORM_REGISTRY.items() if v.category == category}


def all_platforms() -> dict[str, PlatformEntry]:
    return dict(PLATFORM_REGISTRY)
