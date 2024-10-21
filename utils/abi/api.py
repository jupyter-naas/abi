from typing import Union
from fastapi import FastAPI
import uvicorn

class API:
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self.host = host
        self.port = port
        
        self.app = FastAPI()
        
    def run(self):
        config = uvicorn.Config(self.app, host=self.host, port=self.port)
        server = uvicorn.Server(config)
        return server.serve()