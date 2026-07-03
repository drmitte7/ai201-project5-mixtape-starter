# Mixtape Bug Hunt — Submission

## AI Usage
[fill in at the end]

## Codebase Map

### Main Files
- **app.py** — Flask app factory and database setup
- **models.py** — 6 SQLAlchemy models: User, Tag, Song, ListeningEvent, Rating, Playlist, Notification
- **routes/songs.py** — Song sharing, search, and rating endpoints
- **routes/playlists.py** — Playlist creation and song management endpoints
- **routes/users.py** — User profiles, streaks, and notifications endpoints
- **routes/feed.py** — Friends listening now and activity feed endpoints
- **services/streak_service.py** — Listening streak calculation logic
- **services/feed_service.py** — Friends feed and activity feed logic
- **services/search_service.py** — Song search logic
- **services/notification_service.py** — Notification creation and retrieval
- **services/playlist_service.py** — Playlist retrieval logic

### Data Flow Example — Rating a Song
1. User sends POST /songs/<song_id>/rate
2. routes/songs.py receives the request and calls notification_service.rate_song()
3. rate_song() saves a Rating record to the database
4. rate_song() should notify the song's original sharer (Bug 4 — currently missing)
5. Response is returned to the user

### Patterns
- Every route delegates immediately to a service function
- Routes handle input parsing and response formatting
- All business logic lives in services/
- Models define structure only — no business logic

---

## Bug Fixes

### Issue #5 — Last song in playlist never shows up

**How I reproduced it:**
Called GET /playlists/<playlist_id>/songs on a playlist with multiple songs and observed that the last song in the list was always missing from the response.

**Navigation path:**
The README pointed to playlist_service.py as the affected service. I opened get_playlist_songs() and read the return statement, which uses songs[:-1] — Python slice notation that excludes the last element of the list.

**Root cause:**
The return statement uses songs[:-1] instead of songs. In Python, [:-1] means "all elements except the last one." This means the last song in every playlist is always excluded from the response regardless of how many songs the playlist contains.

**Fix and side-effect check:**
Changed songs[:-1] to songs so all songs are returned. Checked get_playlist() and get_user_playlists() — neither touches the songs list, so they are unaffected. Also checked notification_service.add_to_playlist() which calls get_playlist_songs() — it only uses the result to check membership, so returning all songs is correct.
---

### Issue #3 — Duplicate songs in search

**How I reproduced it:**
Queried the song_tags join table directly and confirmed 5 songs have multiple tags. The outerjoin in search_songs() produces one row per tag per song, meaning a song with 3 tags appears 3 times in the raw SQL result.

**Navigation path:**
The README pointed to search_service.py. I opened search_songs() and read the query — it uses outerjoin on song_tags which joins one row per tag. Since Song already loads tags through its relationship, this join is unnecessary and produces duplicates for multi-tag songs.

**Root cause:**
The search query uses .outerjoin(song_tags, Song.id == song_tags.c.song_id) which joins the song_tags association table. For a song with 3 tags, this produces 3 rows in the result — one per tag. SQLAlchemy's ORM deduplicates these at the object level in some cases, but the raw SQL produces duplicates that can appear in the API response for certain query patterns.

**Fix and side-effect check:**
Added .distinct() before .all() to ensure each song appears only once regardless of how many tags it has. Verified search still returns correct results for songs with 0, 1, and 3 tags. The get_song() function is unaffected as it queries by ID directly.

---

### Issue #1 — Streak resets on Sunday

**How I reproduced it:**
[fill in]

**Navigation path:**
[fill in]

**Root cause:**
[fill in]

**Fix and side-effect check:**
[fill in]

---

### Issue #4 — No notification when song is rated

**How I reproduced it:**
[fill in]

**Navigation path:**
[fill in]

**Root cause:**
[fill in]

**Fix and side-effect check:**
[fill in]

---

### Issue #2 — Friends feed shows old activity

**How I reproduced it:**
[fill in]

**Navigation path:**
[fill in]

**Root cause:**
[fill in]

**Fix and side-effect check:**
[fill in]

---

## Git Log Screenshot
[add screenshot here]