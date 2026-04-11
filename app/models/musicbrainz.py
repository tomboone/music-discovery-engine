import warnings

from sqlalchemy.ext.automap import automap_base

MBBase = automap_base()

# These will be None until reflect_mb_tables() is called at app startup
Artist = None
Recording = None
ReleaseGroup = None
Link = None
LinkType = None
ArtistCredit = None
ArtistCreditName = None
ArtistTag = None
Tag = None
LArtistArtist = None
LArtistRecording = None
LArtistRelease = None


def reflect_mb_tables(engine) -> None:
    global Artist, Recording, ReleaseGroup, Link, LinkType
    global ArtistCredit, ArtistCreditName, ArtistTag, Tag
    global LArtistArtist, LArtistRecording, LArtistRelease

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Did not recognize type")
        MBBase.prepare(autoload_with=engine, schema="musicbrainz")

    classes = MBBase.classes
    Artist = classes.get("artist")
    Recording = classes.get("recording")
    ReleaseGroup = classes.get("release_group")
    Link = classes.get("link")
    LinkType = classes.get("link_type")
    ArtistCredit = classes.get("artist_credit")
    ArtistCreditName = classes.get("artist_credit_name")
    ArtistTag = classes.get("artist_tag")
    Tag = classes.get("tag")
    LArtistArtist = classes.get("l_artist_artist")
    LArtistRecording = classes.get("l_artist_recording")
    LArtistRelease = classes.get("l_artist_release")
