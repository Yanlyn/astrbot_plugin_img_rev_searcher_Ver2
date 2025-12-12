from typing import Any, Optional, Union
from pathlib import Path
from typing_extensions import override
from ..response_parser import CopyseekerResponse
from .base_req import BaseSearchReq
from astrbot.api import logger

class Copyseeker(BaseSearchReq[CopyseekerResponse]):
    """
    Copyseeker Search Request (via RapidAPI)
    """
    
    def __init__(self, **request_kwargs: Any):
        self.api_key = request_kwargs.pop("copyseeker_api_key", "")
        super().__init__("https://reverse-image-search-by-copyseeker.p.rapidapi.com", **request_kwargs)
        if not self.api_key:
            logger.warning("[Copyseeker] No API key provided! Please set 'copyseeker_api_key' in config.")

    @override
    async def search(
        self,
        url: Optional[str] = None,
        file: Union[str, bytes, Path, None] = None,
        **kwargs: Any,
    ) -> CopyseekerResponse:
        if not self.api_key:
            return CopyseekerResponse({}, "")

        if file:
            url = await self._upload_image(file)
            
        if not url:
             raise ValueError("[Copyseeker] No URL or File provided.")

        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "reverse-image-search-by-copyseeker.p.rapidapi.com"
        }
        
        # RapidAPI Endpoint takes imageUrl as query param
        params = {"imageUrl": url}
        
        # Import json locally or at top level (assuming top level has imports, or add local import)
        import json
        
        try:
            resp = await self._send_request(
                method="GET",
                endpoint="", 
                headers=headers,
                params=params
            )
            
            if resp.status_code != 200:
                logger.error(f"[Copyseeker] API Error: {resp.status_code} - {resp.text}")
                return CopyseekerResponse({}, resp.url)
                
            return CopyseekerResponse(json.loads(resp.text), resp.url)
            
        except Exception as e:
            logger.error(f"[Copyseeker] Request failed: {e}")
            return CopyseekerResponse({}, "")
