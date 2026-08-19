from services.webcams.adapters.openwebcamdb import OpenWebcamDBAdapter
from services.webcams.WebcamsService import WebcamsService

webcam_service = WebcamsService(adapter=OpenWebcamDBAdapter())

__all__ = ["webcam_service"]
