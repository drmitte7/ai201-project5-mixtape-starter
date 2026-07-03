# Mixtape Bug Hunt — Submission

## AI Usage

I used Claude (AI assistant) in the following ways during this project:

**Instance 1 — Codebase orientation:**
I gave Claude the contents of all service files and asked it to explain what each one does and identify patterns in how the app is organized. This helped me build a mental model of the codebase quickly. I verified the explanations myself by reading the code — the explanations were accurate and matched what I read.

**Instance 2 — Bug diagnosis for Bug 2:**
After narrowing Bug 2 to feed_service.py, I asked Claude to explain the difference between timezone-aware and timezone-naive datetimes in Python and why comparing them can cause incorrect results. Claude explained that SQLite stores datetimes without timezone info, so comparing with a timezone-aware cutoff can behave unexpectedly. I verified this by checking the tzinfo attribute of stored ListeningEvent timestamps in the Flask shell — confirmed they were None.

**Instance 3 — Understanding the outerjoin bug:**
I asked Claude to explain why an outerjoin on a many-to-many association table produces duplicate rows. Claude explained that each tag produces one row in the join result, so a song with 3 tags produces 3 rows. I verified this by querying the song_tags table directly and confirming 5 songs had multiple tags.

In all cases I verified Claude's explanations against the actual code and database state before applying any fix.

---

## Codebase Map

### Main Files

- **app.py** — Flask app factory and database setup
- **models.py** — 7 SQLAlchemy models: User, Tag, Song, ListeningEvent, Rating, Playlist, Notification
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
4. rate_song() notifies the song's original sharer if they weren't the one who rated it
5. Response is returned to the user

### Patterns

- Every route delegates immediately to a service function
- Routes handle input parsing and response formatting
- All business logic lives in services/
- Models define structure only — no business logic

---

## Bug Fixes

### Issue #1 — My listening streak keeps resetting

**How I reproduced it:**
Confirmed in the Flask shell that datetime.weekday() returns 6 for Sunday. The streak condition uses today.weekday() != 6 which evaluates to False on Sundays, preventing the streak from incrementing when a user listens on a Sunday after listening on Saturday.

**Navigation path:**
The README pointed to streak_service.py. I opened update_listening_streak() and read the conditional logic. The elif branch that increments the streak has an extra condition: today.weekday() != 6. I recognized weekday() returns 6 for Sunday and saw immediately that this blocks streak increments every Sunday.

**Root cause:**
Python's datetime.weekday() returns 6 for Sunday. The condition elif days_since_last == 1 and today.weekday() != 6 means the streak only increments if today is NOT Sunday. Any user who listens on consecutive days including a Sunday will have their streak reset to 1 on that Sunday instead of incrementing. The Sunday check has no logical basis in the streak rules described in the docstring.

**Fix and side-effect check:**
Removed the and today.weekday() != 6 condition so the elif branch reads elif days_since_last == 1. This means the streak increments correctly for all consecutive days including Sundays. Checked get_streak() which only reads the streak value — unaffected. Verified the days_since_last == 0 and else branches are unchanged.

---

### Issue #2 — Friends Listening Now shows people from yesterday

**How I reproduced it:**
Checked the timezone info on stored ListeningEvent timestamps in the Flask shell. Confirmed that listened_at values are stored as timezone-naive (tzinfo: None) while the cutoff was calculated using datetime.now(timezone.utc) which is timezone-aware. This mismatch causes incorrect comparisons in SQLite.

**Navigation path:**
The README pointed to feed_service.py. I opened get_friends_listening_now() and read the cutoff calculation. I then checked the stored listened_at values in the database and found they have no timezone info (tzinfo: None). The mismatch between timezone-aware cutoff and timezone-naive stored values was the root cause.

**Root cause:**
The cutoff was calculated with datetime.now(timezone.utc) which produces a timezone-aware datetime. The listened_at values stored in SQLite are timezone-naive (no tzinfo). When SQLite compares a timezone-aware datetime against timezone-naive values, the comparison behaves incorrectly — old events outside the 24-hour window can pass the filter and appear in the feed.

**Fix and side-effect check:**
Changed datetime.now(timezone.utc) to datetime.utcnow() so the cutoff is timezone-naive, matching the stored values. Verified that get_friends_listening_now() now correctly returns only recent events. Checked get_activity_feed() — it does not use a cutoff filter so it is unaffected by this change.

---

### Issue #3 — The same song keeps showing up twice in search

**How I reproduced it:**
Queried the song_tags join table directly and confirmed 5 songs have multiple tags. The outerjoin in search_songs() produces one row per tag per song, meaning a song with 3 tags appears 3 times in the raw SQL result.

**Navigation path:**
The README pointed to search_service.py. I opened search_songs() and read the query — it uses outerjoin on song_tags which joins one row per tag. Since Song already loads tags through its relationship, this join is unnecessary and produces duplicates for multi-tag songs.

**Root cause:**
The search query uses .outerjoin(song_tags, Song.id == song_tags.c.song_id) which joins the song_tags association table. For a song with 3 tags, this produces 3 rows in the result — one per tag. SQLAlchemy's ORM deduplicates these at the object level in some cases, but the raw SQL produces duplicates that can appear in the API response for certain query patterns.

**Fix and side-effect check:**
Added .distinct() before .all() to ensure each song appears only once regardless of how many tags it has. Verified search still returns correct results for songs with 0, 1, and 3 tags. The get_song() function is unaffected as it queries by ID directly.

---

### Issue #4 — I got notified when a friend added my song to a playlist but not when they rated it

**How I reproduced it:**
Rated a song via POST /songs/<song_id>/rate and checked the song sharer's notifications via GET /users/<user_id>/notifications. No song_rated notification appeared, even though a song_added_to_playlist notification correctly appeared when the same song was added to a playlist.

**Navigation path:**
The README pointed to notification_service.py. I compared rate_song() to add_to_playlist() line by line. add_to_playlist() calls create_notification() after saving — rate_song() saves the rating and commits but never calls create_notification(). The missing call was immediately obvious from the structural comparison.

**Root cause:**
The rate_song() function saves the Rating record and commits to the database but never calls create_notification(). The add_to_playlist() function follows the correct pattern — save the action, then notify the song's original sharer if they weren't the one who performed the action. rate_song() was missing the entire notification step.

**Fix and side-effect check:**
Added a create_notification() call after db.session.commit() in rate_song(), following the same pattern as add_to_playlist() — notify song.shared_by only if song.shared_by != user_id. Verified that rating your own song does not generate a notification. Verified that get_notifications() and mark_as_read() are unaffected since they only read and update existing notifications.

---

### Issue #5 — The last song in a playlist never shows up

**How I reproduced it:**
Called GET /playlists/<playlist_id>/songs on a playlist with multiple songs and observed that the last song in the list was always missing from the response.

**Navigation path:**
The README pointed to playlist_service.py as the affected service. I opened get_playlist_songs() and read the return statement, which uses songs[:-1] — Python slice notation that excludes the last element of the list.

**Root cause:**
The return statement uses songs[:-1] instead of songs. In Python, [:-1] means "all elements except the last one." This means the last song in every playlist is always excluded from the response regardless of how many songs the playlist contains.

**Fix and side-effect check:**
Changed songs[:-1] to songs so all songs are returned. Checked get_playlist() and get_user_playlists() — neither touches the songs list, so they are unaffected. Also checked notification_service.add_to_playlist() which calls get_playlist_songs() — it only uses the result to check membership, so returning all songs is correct.

---

## Git Log Screenshot

```
41b71f9 (HEAD -> bugfix/mixtape) fix: use timezone-naive cutoff to match stored listened_at timestamps in feed filter
10ec53c fix: add missing notification when a song is rated
6563baf fix: remove incorrect Sunday exception from streak increment logic
96dc227 fix: add distinct() to search query to prevent duplicate results for multi-tag songs
e307465 fix: return all playlist songs instead of excluding last entry
2dfdeaa (origin/main, origin/HEAD, main) Add .gitignore file and update README with setup instructions
7b64551 initial commit
```

## Regression Test

I wrote a regression test for Bug #5 in `tests/test_playlist_fix.py`.

The test creates a playlist with 3 songs and calls `get_playlist_songs()`. It asserts that all 3 songs are returned and that "Song 3" (the last song) is present in the result.

This test would have **failed against the buggy code** because the original implementation used `songs[:-1]` which excludes the last element — with 3 songs it would return only 2 and "Song 3" would be missing. After the fix using `songs` with no slicing, the test passes correctly.

Run with: `pytest tests/test_playlist_fix.py -v`