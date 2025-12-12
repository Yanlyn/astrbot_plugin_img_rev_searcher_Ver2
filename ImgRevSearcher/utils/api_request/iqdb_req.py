from typing import Any, Optional, Union
from typing_extensions import override

from ..types import FileContent
from ..ext_tools import read_file
from ..response_parser.iqdb_parser import IqdbResponse
from .base_req import BaseSearchReq
from PIL import Image
import io
import os
import time
from pathlib import Path

class Iqdb(BaseSearchReq[IqdbResponse]):
    """
    IQDB 搜索请求类
    支持 2D (iqdb.org) 和 3D (3d.iqdb.org)
    """
    def __init__(
        self,
        is_3d: bool = False,
        **request_kwargs: Any,
    ):
        base_url = "https://3d.iqdb.org" if is_3d else "https://iqdb.org"
        super().__init__(base_url, **request_kwargs)
        self.is_3d = is_3d

    @override
    async def search(
        self,
        url: Optional[str] = None,
        file: FileContent = None,
        force_gray: bool = False,
        **kwargs: Any,
    ) -> IqdbResponse:
        data = {}
        files = None
        
        if force_gray:
            data["forcegray"] = "on"

        if url:
            data["url"] = url
        elif file:
            filename = "image.jpg"
            if hasattr(file, 'name'):
                filename = file.name
            
            
            file_content = read_file(file)
            
            # Check IQDB limits
            if len(file_content) > 8192 * 1024:
                raise ValueError("IQDB limit: File size must be under 8192 KB")
            
            try:
                img = Image.open(io.BytesIO(file_content))
                w, h = img.size
                if w > 7500 or h > 7500:
                    raise ValueError(f"IQDB limit: Image dimensions ({w}x{h}) exceed 7500x7500")
            except Exception:
                pass # Ignore if not an image or PIL fails, let IQDB handle it
                
            files = {"file": (filename, file_content, "image/jpeg")}
        else:
            raise ValueError("Must provide url or file")

        # IQDB 统一使用 POST (即使是 URL)
        resp = await self._send_request(
            method="post",
            data=data,
            files=files
        )
        
        
        # Debug: Dump HTML
        try:
             # Basic check: if "No relevant matches" in text
             if "No relevant matches" in resp.text and "Best match" not in resp.text:
                 pass # normal no match
             else:
                 # Dumping for analysis regardless, or maybe just when suspicious?
                 # User says "No results" but browser has results.
                 # Let's dump always for now to a rolling file
                 save_dir = Path("data/plugins/img_rev_searcher/debug")
                 save_dir.mkdir(parents=True, exist_ok=True)
                 with open(save_dir / f"iqdb_dump_{int(time.time())}.html", "w", encoding="utf-8") as f:
                     f.write(resp.text)
        except Exception:
             pass

        return IqdbResponse(resp.text, resp.url)
