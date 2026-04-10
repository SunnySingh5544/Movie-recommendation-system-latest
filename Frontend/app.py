import streamlit as st
import requests

BASE_URL  = "http://127.0.0.1:8000"
# Backend fires ~11 TMDB calls in parallel — give it up to 30 s.
# The old 8 s was shorter than needed, causing the timeout error.
TIMEOUT   = 30
TMDB_IMG  = "https://image.tmdb.org/t/p/w500"
TMDB_IMG_ORIG = "https://image.tmdb.org/t/p/original"

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CineMatch",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500&display=swap');

/* ---- reset / base ---- */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background: #0a0a0f;
    color: #e8e4dc;
}
.block-container { padding: 2rem 3rem 4rem; max-width: 1400px; }

/* ---- hero title ---- */
.hero-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: clamp(3rem, 8vw, 6rem);
    letter-spacing: 0.08em;
    background: linear-gradient(135deg, #f5c518 0%, #ff6b35 60%, #c2185b 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1;
    margin-bottom: 0.2rem;
}
.hero-sub {
    font-size: 0.95rem;
    color: #888;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    margin-bottom: 2.5rem;
}

/* ---- search bar ---- */
div[data-testid="stTextInput"] input {
    background: #16161f !important;
    border: 1.5px solid #2a2a3a !important;
    border-radius: 50px !important;
    color: #e8e4dc !important;
    font-size: 1rem !important;
    padding: 0.75rem 1.5rem !important;
    transition: border-color 0.2s;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #f5c518 !important;
    box-shadow: 0 0 0 3px rgba(245,197,24,0.15) !important;
}

/* ---- section headings ---- */
.section-heading {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.8rem;
    letter-spacing: 0.1em;
    color: #f5c518;
    margin: 2.5rem 0 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.section-heading::after {
    content: '';
    flex: 1;
    height: 1px;
    background: linear-gradient(to right, #f5c518 0%, transparent 80%);
    margin-left: 0.75rem;
}

/* ---- movie card ---- */
.movie-card {
    position: relative;
    border-radius: 12px;
    overflow: hidden;
    background: #12121a;
    transition: transform 0.25s ease, box-shadow 0.25s ease;
    cursor: pointer;
}
.movie-card:hover {
    transform: translateY(-6px) scale(1.02);
    box-shadow: 0 20px 40px rgba(0,0,0,0.7), 0 0 0 1px rgba(245,197,24,0.25);
}
.movie-card img {
    width: 100%;
    display: block;
    aspect-ratio: 2/3;
    object-fit: cover;
}
.movie-card-label {
    padding: 0.6rem 0.75rem;
    font-size: 0.78rem;
    font-weight: 500;
    color: #ccc;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    background: #12121a;
}
.movie-card-badge {
    position: absolute;
    top: 8px;
    right: 8px;
    background: rgba(245,197,24,0.9);
    color: #000;
    font-size: 0.65rem;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 20px;
    letter-spacing: 0.05em;
}

/* ---- detail panel ---- */
.detail-panel {
    background: linear-gradient(135deg, #14141e 0%, #1a1225 100%);
    border: 1px solid #2a2a3a;
    border-radius: 16px;
    padding: 2rem;
    margin: 1.5rem 0;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.detail-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 2.8rem;
    letter-spacing: 0.06em;
    color: #f5c518;
    line-height: 1.1;
}
.detail-meta {
    font-size: 0.82rem;
    color: #888;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin: 0.4rem 0 1rem;
}
.detail-overview {
    font-size: 0.97rem;
    line-height: 1.7;
    color: #c8c4bc;
    margin-top: 0.75rem;
}
.genre-pill {
    display: inline-block;
    background: rgba(245,197,24,0.1);
    border: 1px solid rgba(245,197,24,0.3);
    color: #f5c518;
    font-size: 0.72rem;
    font-weight: 500;
    padding: 3px 10px;
    border-radius: 20px;
    margin: 2px 3px 2px 0;
    letter-spacing: 0.08em;
}
.rating-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(245,197,24,0.15);
    border: 1px solid rgba(245,197,24,0.4);
    color: #f5c518;
    font-size: 1rem;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 8px;
}

/* ---- poster image ---- */
.poster-img {
    border-radius: 12px;
    box-shadow: -8px 8px 32px rgba(0,0,0,0.7);
    width: 100%;
}

/* ---- no poster placeholder ---- */
.no-poster {
    background: #1a1a28;
    border: 1px dashed #333;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 300px;
    color: #555;
    font-size: 0.85rem;
}

/* ---- error / warning ---- */
div[data-testid="stAlert"] {
    border-radius: 10px !important;
}

/* ---- scrollbar ---- */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0a0a0f; }
::-webkit-scrollbar-thumb { background: #2a2a3a; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)


# ── Helper: render a movie grid ───────────────────────────────────────────────
def render_movie_grid(movies, cols=5, badge_text=None):
    """
    Expects each movie dict to have at least:
        title, poster_path  (relative TMDB path, e.g. /abc.jpg)
    OR  poster_url          (full URL)
    """
    columns = st.columns(cols)
    for i, movie in enumerate(movies):
        with columns[i % cols]:
            poster = movie.get("poster_url") or (
                TMDB_IMG + movie["poster_path"] if movie.get("poster_path") else None
            )
            title = movie.get("title", "Unknown")
            html = '<div class="movie-card">'
            if poster:
                html += f'<img src="{poster}" alt="{title}" loading="lazy">'
            else:
                html += '<div class="no-poster">No Image</div>'
            if badge_text:
                html += f'<span class="movie-card-badge">{badge_text}</span>'
            html += f'<div class="movie-card-label">{title}</div></div>'
            st.markdown(html, unsafe_allow_html=True)


# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown('<div class="hero-title">CineMatch</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Discover · Explore · Obsess</div>', unsafe_allow_html=True)

# ── SEARCH ────────────────────────────────────────────────────────────────────
query = st.text_input("Search", placeholder="🔍  Search for a movie…", label_visibility="collapsed")

# ── SEARCH RESULTS ────────────────────────────────────────────────────────────
if query:
    with st.spinner("Fetching results…"):
        try:
            res = requests.get(f"{BASE_URL}/movie/search", params={"query": query}, timeout=TIMEOUT)

            if res.status_code != 200:
                st.error("Backend returned an error ❌")
            else:
                data = res.json()

                if "error" in data:
                    st.warning("No movie found for that search. Try a different title.")
                else:
                    movie = data["movie_details"]

                    # ── Detail panel ──────────────────────────────────────────
                    st.markdown('<div class="section-heading">🎬 Movie Details</div>',
                                unsafe_allow_html=True)

                    left, right = st.columns([1, 2.8], gap="large")

                    with left:
                        poster_url = movie.get("poster_url") or (
                            TMDB_IMG + movie["poster_path"] if movie.get("poster_path") else None
                        )
                        if poster_url:
                            st.markdown(
                                f'<img class="poster-img" src="{poster_url}" alt="{movie["title"]}">',
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown('<div class="no-poster">No Poster Available</div>',
                                        unsafe_allow_html=True)

                    with right:
                        rating = movie.get("vote_average")
                        release = movie.get("release_date", "")[:4] if movie.get("release_date") else ""
                        runtime = movie.get("runtime")
                        genres = movie.get("genres", [])  # list of strings

                        st.markdown(
                            f'<div class="detail-title">{movie["title"]}</div>',
                            unsafe_allow_html=True,
                        )

                        meta_parts = [p for p in [release, f"{runtime} min" if runtime else None] if p]
                        st.markdown(
                            f'<div class="detail-meta">{" · ".join(meta_parts)}</div>',
                            unsafe_allow_html=True,
                        )

                        if rating:
                            st.markdown(
                                f'<span class="rating-badge">⭐ {rating:.1f} / 10</span>',
                                unsafe_allow_html=True,
                            )

                        if genres:
                            pills = "".join(
                                f'<span class="genre-pill">{g}</span>' for g in genres
                            )
                            st.markdown(f"<div style='margin:0.75rem 0'>{pills}</div>",
                                        unsafe_allow_html=True)

                        overview = movie.get("overview", "")
                        if overview:
                            st.markdown(
                                f'<div class="detail-overview">{overview}</div>',
                                unsafe_allow_html=True,
                            )

                    # ── Recommendations ───────────────────────────────────────
                    recs = data.get("recommendations", [])
                    if recs:
                        st.markdown(
                            '<div class="section-heading">✨ You Might Also Like</div>',
                            unsafe_allow_html=True,
                        )

                        # Normalise: backend may return strings OR dicts
                        normalised = []
                        for item in recs:
                            if isinstance(item, str):
                                # Only a name came back — show as card without image
                                normalised.append({"title": item, "poster_path": None})
                            elif isinstance(item, dict):
                                normalised.append(item)

                        render_movie_grid(normalised, cols=5)

        except requests.exceptions.ConnectionError:
            st.error("Cannot reach the backend. Make sure it's running on port 8000 ❌")
        except Exception as e:
            st.error(f"Unexpected error: {e}")

# ── TRENDING (shown when no search is active) ─────────────────────────────────
if not query:
    st.markdown('<div class="section-heading">🔥 Trending Now</div>', unsafe_allow_html=True)

    try:
        res = requests.get(f"{BASE_URL}/home", timeout=TIMEOUT)

        if res.status_code == 200:
            trending = res.json()[:10]
            render_movie_grid(trending, cols=5, badge_text="TRENDING")
        else:
            st.error("Failed to load trending movies ❌")

    except requests.exceptions.ConnectionError:
        st.error("Cannot reach the backend. Make sure it's running on port 8000 ❌")
    except Exception as e:
        st.error(f"Unexpected error: {e}")