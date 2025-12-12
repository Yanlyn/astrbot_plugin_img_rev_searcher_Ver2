from typing import Any, Optional, Union
from typing_extensions import override

from ..types import FileContent
from ..ext_tools import read_file
from ..response_parser.ascii2d_parser import Ascii2DResponse
from .base_req import BaseSearchReq
from astrbot.api import logger
import os
import time
import re
from pathlib import Path

from curl_cffi.requests import Session
import asyncio
import requests # For Litterbox

class Ascii2D(BaseSearchReq[Ascii2DResponse]):
    """
    Ascii2D 搜索请求类
    支持颜色搜索 (默认) 和 特征搜索 (bovw)
    """
    def __init__(
        self,
        base_url: str = "https://ascii2d.net",
        bovw: bool = False,
        **request_kwargs: Any,
    ):
        base_url = f"{base_url}/search"
        super().__init__(base_url, **request_kwargs)
        self.bovw = bovw

    @override
    async def search(
        self,
        url: Optional[str] = None,
        file: FileContent = None,
        **kwargs: Any,
    ) -> Ascii2DResponse:
        
        # Robust Workflow:
        # 1. Upload to Litterbox (standard requests) to get clean URL
        # 2. Use curl_cffi to Probe Ascii2D (cookies/tokens) -> Search URI -> Follow Redirect
        
        try:
            filename = "image.jpg"
            file_data = None
            
            # Prepare data
            if url:
                 # If URL provided, skip litterbox if it's public? 
                 # But safer to re-upload if original host blocks hotlinking? 
                 # Simple path: if url provided, use it directly first.
                 pass
            elif file:
                filename = "image.jpg"
                if hasattr(file, 'name') and file.name:
                    filename = file.name
                file_data = read_file(file)
            else:
                raise ValueError("Must provide url or file")

            def _sync_ascii2d_search(base_url, file_name, file_bytes, input_url):
                 image_url = input_url
                 
                 # A. Upload to Litterbox (if file)
                 if file_bytes:
                     try:
                         logger.info("[Ascii2D] Uploading to Litterbox (1h temp host)...")
                         files = {'fileToUpload': (file_name, file_bytes, 'image/jpeg')}
                         data = {'reqtype': 'fileupload', 'time': '1h'}
                         lb_resp = requests.post(
                             "https://litterbox.catbox.moe/resources/internals/api.php",
                             files=files,
                             data=data,
                             timeout=60
                         )
                         if lb_resp.status_code != 200 or not lb_resp.text.startswith("http"):
                             raise Exception(f"Litterbox upload failed: {lb_resp.text[:100]}")
                         
                         image_url = lb_resp.text.strip()
                         logger.info(f"[Ascii2D] Litterbox URL: {image_url}")
                     except Exception as e:
                         logger.error(f"[Ascii2D] Intermediate upload failed: {e}")
                         raise e
                 
                 # B. Search ASCII2D via URI
                 # Use curl_cffi Session to impersonate browser (Bypasses Cloudflare UAM)
                 with Session(impersonate="chrome120", verify=False) as s:
                      headers = {
                          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                          "Origin": "https://ascii2d.net",
                          "Referer": "https://ascii2d.net/",
                      }
                      
                      # 1. PROBE (GET /)
                      logger.info(f"[Ascii2D] Probing {base_url.replace('/search', '')}...")
                      probe = s.get("https://ascii2d.net/", headers=headers, timeout=30)
                      if probe.status_code == 403: # Should be handled by impersonate, but check
                          raise Exception("Probe 403 Forbidden (Cloudflare Blocked)")
                      
                      token = None
                      match = re.search(r'name="csrf-token" content="([^"]+)"', probe.text)
                      if match:
                          token = match.group(1)
                      
                      # 2. POST URI
                      # 2. POST URI with Retry
                      logger.info(f"[Ascii2D] Searching URI: {image_url}")
                      payload = {
                          "utf8": "✓",
                          "uri": image_url
                      }
                      if token:
                          payload["authenticity_token"] = token
                      
                      max_retries = 3
                      post_resp = None
                      
                      for attempt in range(max_retries):
                          try:
                              post_resp = s.post(
                                 f"{base_url}/uri", 
                                 data=payload,
                                 headers=headers,
                                 allow_redirects=False,
                                 timeout=60
                              )
                              if post_resp.status_code in [502, 503, 504]:
                                  logger.warning(f"[Ascii2D] Search Attempt {attempt+1} failed ({post_resp.status_code}). Retrying...")
                                  import time
                                  time.sleep(2)
                                  continue
                              break
                          except Exception as e:
                              logger.warning(f"[Ascii2D] Attempt {attempt+1} Error: {e}")
                              if attempt == max_retries -1:
                                  raise e
                              import time
                              time.sleep(2)
                      
                      if not post_resp:
                          raise Exception("Ascii2D Search Failed (Network Error)")

                      redirect_url = None
                      # Ascii2D usually redirects to /search/color/HASH
                      if post_resp.status_code in [301, 302, 303, 307, 308]:
                          redirect_url = post_resp.headers.get("Location")
                      elif post_resp.status_code == 200:
                          redirect_url = str(post_resp.url)
                      else:
                          raise Exception(f"URI Search failed: {post_resp.status_code}")
                      
                      if not redirect_url:
                          raise Exception("No redirect URL found (Ascii2D)")
                          
                      if not redirect_url.startswith("http"):
                          redirect_url = f"https://ascii2d.net{redirect_url}"
                          
                      # 3. FETCH RESULT
                      logger.info(f"[Ascii2D] Fetching result: {redirect_url}")
                      
                      # Handle BOVW swap (URL manipulation)
                      # 'self' is not available here easily unless passed, logic moved to wrapper or here?
                      # We return the initial result, wrapper handles BOVW swap logic OR we return raw and wrapper handles.
                      # Let's return raw first.
                      
                      result_resp = s.get(redirect_url, headers=headers)
                      return result_resp.text, str(result_resp.url)

            # Execution
            resp_text, resp_url = await asyncio.to_thread(
                _sync_ascii2d_search, 
                self.base_url, # .../search
                filename,
                file_data,
                url
            )
            
            # Handle BOVW swap
            if self.bovw and "/color/" in resp_url:
                 new_url = resp_url.replace("/color/", "/bovw/")
                 logger.info(f"[Ascii2D] Switching to BOVW: {new_url}")
                 # Use quick request (curl_cffi) to get this too? Or simple requests?
                 # Need to reuse session cookies?
                 # Since it's a GET, impersonation shouldn't be strictly required IF we have the URL, 
                 # BUT Ascii2D might check. Better reuse logic or just assume standard result format.
                 # Actually, we can just return the URL and let parser handle? No, parser needs content.
                 # Let's do a quick fetch
                 async with Session(impersonate="chrome120", verify=False) as s2:
                     r2 = await s2.get(new_url)
                     return Ascii2DResponse(r2.text, str(r2.url))
            
            return Ascii2DResponse(resp_text, resp_url)

        except Exception as e:
            logger.error(f"[Ascii2D] Search failed: {e}")
            raise e