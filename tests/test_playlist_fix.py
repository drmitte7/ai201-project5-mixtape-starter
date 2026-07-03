"""
Regression test for Bug #5 — last song in playlist was excluded.

This test would have failed against the buggy code because get_playlist_songs()
used songs[:-1] which excludes the last element. With 3 songs it would return
only 2, and "Song 3" would be missing.
"""
import pytest
from app import create_app, db
from models import User, Song, Playlist, playlist_entries
from services.playlist_service import get_playlist_songs
from datetime import datetime, timezone


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_last_song_included(app):
    """The last song in a playlist must be included in get_playlist_songs()."""
    with app.app_context():
        user = User(username="testuser", email="test@test.com")
        db.session.add(user)
        db.session.flush()

        songs = [
            Song(title=f"Song {i}", artist="Artist", shared_by=user.id)
            for i in range(1, 4)
        ]
        db.session.add_all(songs)
        db.session.flush()

        playlist = Playlist(name="Test Playlist", created_by=user.id)
        db.session.add(playlist)
        db.session.flush()

        for i, song in enumerate(songs):
            db.session.execute(
                playlist_entries.insert().values(
                    playlist_id=playlist.id,
                    song_id=song.id,
                    position=i + 1,
                    added_by=user.id,
                    added_at=datetime.now(timezone.utc),
                )
            )
        db.session.commit()

        result = get_playlist_songs(playlist.id)
        assert len(result) == 3, f"Expected 3 songs, got {len(result)}"
        titles = [s["title"] for s in result]
        assert "Song 3" in titles, "Last song 'Song 3' was missing from playlist"