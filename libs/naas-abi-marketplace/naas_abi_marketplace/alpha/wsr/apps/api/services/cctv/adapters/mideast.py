"""
Middle East / theater CCTV adapter — hardcoded curated cameras.

Strict sourcing policy: only confirmed-live streams.
All entries verified February 2026.
"""

from ports.models import CCTVCamera
from services.cctv.CCTVPort import ICCTVAdapter

_CAMERAS: list[CCTVCamera] = [
    # ── Israel ─────────────────────────────────────────────────────────────────
    CCTVCamera(
        id="me-western-wall",
        name="Western Wall — Jerusalem Old City",
        lat=31.7767, lon=35.2345,
        city="Jerusalem", country="Israel",
        imageUrl="",
        videoUrl="https://www.youtube.com/embed/bb46Zsx5988?autoplay=1&mute=1",
        type="youtube", source="openwebcamdb",
    ),
    CCTVCamera(
        id="me-mount-zion",
        name="Mount Zion — Jerusalem",
        lat=31.7720, lon=35.2286,
        city="Jerusalem", country="Israel",
        imageUrl="",
        videoUrl="https://www.ipcamlive.com/player/player.php?alias=mtzionlive&autoplay=1",
        type="youtube", source="openwebcamdb",
    ),
    CCTVCamera(
        id="me-tel-aviv-axis",
        name="Tel Aviv — Open IP Cam (Axis MJPEG)",
        lat=32.0989, lon=34.7800,
        city="Tel Aviv", country="Israel",
        imageUrl="http://62.219.135.70:1000/mjpg/video.mjpg",
        videoUrl="",
        type="hls", source="openwebcamdb",
    ),
    # ── Lebanon ────────────────────────────────────────────────────────────────
    CCTVCamera(
        id="me-beirut-lebcam",
        name="Beirut — LebCam Traffic Network",
        lat=33.8938, lon=35.5018,
        city="Beirut", country="Lebanon",
        imageUrl="",
        videoUrl="https://www.livelebcams.com/",
        type="youtube", source="openwebcamdb",
    ),
    # ── UAE / Gulf ─────────────────────────────────────────────────────────────
    CCTVCamera(
        id="me-dubai-marina-skyline",
        name="Dubai Marina — Princess Tower (SkylineWebcams)",
        lat=25.0836, lon=55.1414,
        city="Dubai", country="UAE",
        imageUrl="",
        videoUrl=(
            "https://www.skylinewebcams.com/webcam/united-arab-emirates/"
            "dubai/dubai/dubai-marina.html"
        ),
        type="youtube", source="openwebcamdb",
    ),
    CCTVCamera(
        id="me-dubai-palm-fairmont",
        name="Dubai — Palm Jumeirah Live (Fairmont The Palm)",
        lat=25.1161, lon=55.1389,
        city="Dubai", country="UAE",
        imageUrl="",
        videoUrl="https://www.youtube.com/embed/7dE4IjDQJmE?autoplay=1&mute=1",
        type="youtube", source="openwebcamdb",
    ),
]


class MideastAdapter(ICCTVAdapter):
    async def fetch(self) -> list[CCTVCamera]:
        return _CAMERAS
