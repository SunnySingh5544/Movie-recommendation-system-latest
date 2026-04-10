from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import pandas as pd
import pickle
import numpy as np
import httpx
import os
from dotenv import load_dotenv
from sklearn.metrics.pairwise import cosine_similarity

# =========================
# ENV
# =========================
load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
print(f"🔑 TMDB_API_KEY loaded: {'YES → ' + TMDB_API_KEY[:6] + '...' if TMDB_API_KEY else 'NO ❌'}")
BASE_URL = "https://api.themoviedb.org/3"
IMG_URL  = "https://image.tmdb.org/t/p/w500"

# =========================
# SHARED HTTP CLIENT
# =========================
http_client: httpx.AsyncClient = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
    yield
    await http_client.aclose()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# LOAD YOUR 3 MODEL FILES
# =========================
print("Loading model files...")

# 1. df.pkl — your movies dataframe (CSV format)
try:
    df = pd.read_csv("df.pkl")
    # Normalize title column name
    df.columns = [c.strip().lower() for c in df.columns]
    print(f"✅ df.pkl → {len(df)} rows | columns: {list(df.columns)}")
except Exception as e:
    print(f"❌ df.pkl failed: {e}")
    df = pd.DataFrame({"title": []})

# 2. tfidf_matrix.pkl — sparse TF-IDF matrix (rows = movies, cols = words)
try:
    with open("tfidf_matrix.pkl", "rb") as f:
        tfidf_matrix = pickle.load(f)
    print(f"✅ tfidf_matrix.pkl → shape: {tfidf_matrix.shape}")
except Exception as e:
    print(f"❌ tfidf_matrix.pkl failed: {e}")
    tfidf_matrix = None

# 3. indices.pkl — maps movie title → integer row index in tfidf_matrix
try:
    with open("indices.pkl", "rb") as f:
        indices = pickle.load(f)
    # Convert to dict for fast O(1) lookup regardless of original type
    if hasattr(indices, "to_dict"):
        indices_dict = {str(k).lower().strip(): int(v) for k, v in indices.items()}
    elif isinstance(indices, dict):
        indices_dict = {str(k).lower().strip(): int(v) for k, v in indices.items()}
    else:
        indices_dict = {}
    print(f"✅ indices.pkl → {len(indices_dict)} entries")
except Exception as e:
    print(f"❌ indices.pkl failed: {e}")
    indices_dict = {}

# Detect title column in df
TITLE_COL = next(
    (c for c in df.columns if "title" in c.lower()),
    df.columns[0] if len(df.columns) > 0 else "title"
)

# Detect movie_id column in df (optional — used for direct TMDB lookup)
ID_COL = next(
    (c for c in df.columns if c in ["movie_id", "id", "tmdb_id", "movieid"]),
    None
)
print(f"📋 Using → title_col='{TITLE_COL}'  id_col='{ID_COL}'")


# =========================
# RECOMMENDER
# Uses YOUR tfidf_matrix + indices for cosine similarity
# =========================
def recommend(title: str) -> list[dict]:
    if tfidf_matrix is None:
        print("⚠️ tfidf_matrix not loaded, skipping recommendations")
        return []

    key = title.lower().strip()

    # Exact match first
    idx = indices_dict.get(key)

    # Fuzzy fallback — find closest title in df
    if idx is None:
        matches = df[df[TITLE_COL].str.lower().str.contains(key, na=False, regex=False)]
        if matches.empty:
            print(f"⚠️ '{title}' not found in indices or df")
            return []
        fallback_title = matches.iloc[0][TITLE_COL]
        idx = indices_dict.get(fallback_title.lower().strip())
        if idx is None:
            print(f"⚠️ '{fallback_title}' found in df but not in indices")
            return []

    # Compute cosine similarity between this movie and all others
    movie_vector = tfidf_matrix[idx]
    scores = cosine_similarity(movie_vector, tfidf_matrix).flatten()

    # Sort descending, skip index 0 (the movie itself), take top 10
    top_indices = np.argsort(scores)[::-1]
    top_indices = [i for i in top_indices if i != idx][:10]

    results = []
    for i in top_indices:
        row  = df.iloc[i]
        mid  = row[ID_COL] if ID_COL and pd.notna(row.get(ID_COL)) else None
        results.append({
            "title":    row[TITLE_COL],
            "movie_id": int(mid) if mid is not None else None,
            "score":    round(float(scores[i]), 4),
        })

    print(f"🎬 Top recs for '{title}': {[r['title'] for r in results]}")
    return results


# =========================
# TMDB HELPERS
# =========================
async def tmdb_get(path: str, params: dict = {}) -> dict:
    try:
        res = await http_client.get(
            f"{BASE_URL}{path}",
            params={"api_key": TMDB_API_KEY, **params},
        )
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"TMDB ERROR [{path}]: {e}")
        return {}


async def fetch_by_id(movie_id: int) -> dict:
    """Direct TMDB lookup by ID — always gets the right poster."""
    return await tmdb_get(f"/movie/{movie_id}")


async def fetch_by_title(title: str) -> dict:
    """Title search fallback when movie_id is not in df."""
    data = await tmdb_get("/search/movie", {"query": title})
    results = data.get("results", [])
    return results[0] if results else {}


def format_movie(m: dict, extra: dict = {}) -> dict:
    poster_path = m.get("poster_path")
    return {
        "title":        m.get("title"),
        "poster_path":  poster_path,
        "poster_url":   (IMG_URL + poster_path) if poster_path else None,
        "vote_average": round(m.get("vote_average") or 0, 1),
        "release_date": m.get("release_date", ""),
        **extra,
    }


# =========================
# ROUTES
# =========================
@app.get("/")
def root():
    return {"message": "🎬 CineMatch API running"}


@app.get("/debug")
def debug():
    """Verify all 3 files loaded correctly. Open in browser after starting server."""
    return {
        "df_rows":        len(df),
        "df_columns":     list(df.columns),
        "title_col":      TITLE_COL,
        "id_col":         ID_COL,
        "tfidf_loaded":   tfidf_matrix is not None,
        "tfidf_shape":    list(tfidf_matrix.shape) if tfidf_matrix is not None else None,
        "indices_count":  len(indices_dict),
        "sample_titles":  df[TITLE_COL].head(5).tolist(),
        "sample_indices": dict(list(indices_dict.items())[:3]),
    }


@app.get("/home")
async def get_home():
    """Trending movies for homepage."""
    data = await tmdb_get("/trending/movie/week")
    return [format_movie(m) for m in data.get("results", [])[:10]]


@app.get("/movie/search")
async def search(query: str):
    # 1. Search TMDB for the query
    search_data = await tmdb_get("/search/movie", {"query": query})
    results     = search_data.get("results", [])

    if not results:
        return {"error": "Movie not found"}

    base     = results[0]
    movie_id = base["id"]

    # 2. Get recommendations using YOUR trained TF-IDF + cosine similarity model
    recs = recommend(base.get("title", ""))

    # 3. Fire all TMDB calls in parallel:
    #    - full details for main movie (genres, runtime)
    #    - poster for each recommendation (by ID if available, else by title)
    details_task = fetch_by_id(movie_id)
    rec_tasks = [
        fetch_by_id(r["movie_id"]) if r["movie_id"]
        else fetch_by_title(r["title"])
        for r in recs
    ]

    all_results = await asyncio.gather(details_task, *rec_tasks)
    details     = all_results[0]
    rec_fetched = all_results[1:]

    # 4. Build response
    movie_details = format_movie(base, extra={
        "overview": base.get("overview"),
        "runtime":  details.get("runtime"),
        "genres":   [g["name"] for g in details.get("genres", [])],
    })

    recommendations = []
    for rec, fetched in zip(recs, rec_fetched):
        if fetched:
            recommendations.append(format_movie(fetched, extra={
                "similarity_score": rec["score"]
            }))
        else:
            recommendations.append({
                "title":            rec["title"],
                "poster_path":      None,
                "poster_url":       None,
                "vote_average":     None,
                "release_date":     "",
                "similarity_score": rec["score"],
            })

    return {
        "movie_details":   movie_details,
        "recommendations": recommendations,
    }