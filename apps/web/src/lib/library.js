// Auralith has no artist table: an artist is every track that shares a normalized
// name, so the artist page and grouped search are built from library metadata alone.

export const UNKNOWN_ARTIST = "Artista desconocido";
export const UNKNOWN_ALBUM = "Sin álbum";

function fold(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

export function artistName(track) {
  const value = typeof track?.artist === "string" ? track.artist.trim() : "";
  return value || UNKNOWN_ARTIST;
}

export function albumName(track) {
  const value = typeof track?.album === "string" ? track.album.trim() : "";
  return value || UNKNOWN_ALBUM;
}

// "The Beatles" and "Beatles" should land on the same page.
export function artistKeyForName(name) {
  return fold(name).replace(/^the\s+/, "");
}

export function artistKey(track) {
  return artistKeyForName(artistName(track));
}

function compareAlbums(a, b) {
  return (a.year ?? 9999) - (b.year ?? 9999) || a.name.localeCompare(b.name, "es");
}

export function buildArtistIndex(tracks) {
  const artists = new Map();
  for (const track of tracks || []) {
    const key = artistKey(track);
    let artist = artists.get(key);
    if (!artist) {
      artist = { key, name: artistName(track), cover_url: null, tracks: [], albums: new Map() };
      artists.set(key, artist);
    }
    artist.tracks.push(track);
    if (!artist.cover_url && track.cover_url) artist.cover_url = track.cover_url;

    const foldedAlbum = fold(albumName(track));
    let album = artist.albums.get(foldedAlbum);
    if (!album) {
      album = {
        key: `${key}::${foldedAlbum}`,
        name: albumName(track),
        year: null,
        cover_url: null,
        tracks: []
      };
      artist.albums.set(foldedAlbum, album);
    }
    album.tracks.push(track);
    if (!album.year && track.year) album.year = track.year;
    if (!album.cover_url && track.cover_url) album.cover_url = track.cover_url;
  }
  return [...artists.values()]
    .map((artist) => ({
      ...artist,
      albums: [...artist.albums.values()].sort(compareAlbums),
      duration: artist.tracks.reduce((total, track) => total + (Number(track.duration) || 0), 0)
    }))
    .sort((a, b) => a.name.localeCompare(b.name, "es"));
}

// Accepting a prebuilt index keeps typing cheap: the caller already groups the
// library once per track change, instead of once per keystroke.
export function searchLibrary(tracks, query, prebuiltIndex = null) {
  const needle = fold(query);
  if (!needle) return { artists: [], albums: [], tracks: [] };

  const index = prebuiltIndex || buildArtistIndex(tracks);
  const matchedTracks = (tracks || []).filter((track) =>
    [track.title, track.artist, track.album, track.genre].some((value) =>
      fold(value).includes(needle)
    )
  );
  const matchedIds = new Set(matchedTracks.map((track) => track.id));
  const artists = index.filter((artist) => fold(artist.name).includes(needle));

  const albums = [];
  for (const artist of index) {
    for (const album of artist.albums) {
      if (
        fold(album.name).includes(needle) ||
        album.tracks.some((track) => matchedIds.has(track.id))
      ) {
        albums.push({ ...album, artist: artist.name, artist_key: artist.key });
      }
    }
  }
  albums.sort(
    (a, b) => a.name.localeCompare(b.name, "es") || a.artist.localeCompare(b.artist, "es")
  );
  matchedTracks.sort((a, b) =>
    String(a.title || "").localeCompare(String(b.title || ""), "es")
  );

  // Keep the results page bounded: a single letter can match the whole library.
  return {
    artists: artists.slice(0, 12),
    albums: albums.slice(0, 24),
    tracks: matchedTracks.slice(0, 100)
  };
}

export function shuffleTracks(tracks) {
  const copy = [...(tracks || [])];
  for (let index = copy.length - 1; index > 0; index -= 1) {
    const swap = Math.floor(Math.random() * (index + 1));
    [copy[index], copy[swap]] = [copy[swap], copy[index]];
  }
  return copy;
}
