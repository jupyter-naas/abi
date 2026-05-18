from services.cctv.adapters.london import LondonAdapter
from services.cctv.adapters.mideast import MideastAdapter
from services.cctv.adapters.nyc import NYCAdapter
from services.cctv.CCTVService import CCTVService
from services.webcams.adapters.openwebcamdb import OpenWebcamDBAdapter

cctv_service = CCTVService(
    adapters=[
        MideastAdapter(),
        NYCAdapter(),
        LondonAdapter(),
        OpenWebcamDBAdapter(),
    ]
)

__all__ = ["cctv_service"]
