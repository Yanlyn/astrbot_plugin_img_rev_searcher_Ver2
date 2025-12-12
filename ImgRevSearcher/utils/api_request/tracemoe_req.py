import json
from typing import Any, Optional, Union, Dict
from typing_extensions import override

from ..types import FileContent
from ..ext_tools import read_file
from ..response_parser.tracemoe_parser import TraceMoeResponse
from .base_req import BaseSearchReq
from astrbot.api import logger
import time
from pathlib import Path

ANIME_INFO_QUERY = """
query ($id: Int) {
  Media (id: $id, type: ANIME) {
    id
    title {
      native
      romaji
      english
    }
    coverImage {
      large
    }
    isAdult
  }
}
"""

class TraceMoe(BaseSearchReq[TraceMoeResponse]):
    """
    TraceMoe 搜索请求类
    """
    def __init__(
        self,
        base_url: str = "https://api.trace.moe",
        anilist_url: str = "https://graphql.anilist.co", # Use official endpoint
        api_key: Optional[str] = None,
        **request_kwargs: Any,
    ):
        base_url = f"{base_url}/search"
        super().__init__(base_url, **request_kwargs)
        self.anilist_url = anilist_url
        self.api_key = api_key

    @override
    async def search(
        self,
        url: Optional[str] = None,
        file: FileContent = None,
        **kwargs: Any,
    ) -> TraceMoeResponse:
        params = {}
        if self.api_key:
            params["key"] = self.api_key
        
        # 允许剪裁图片 (cutBorders)
        if kwargs.get("cut_borders"):
             params["cutBorders"] = ""

        files = None
        if url:
            params["url"] = url
        elif file:
            filename = "image.jpg"
            if hasattr(file, 'name'):
                filename = file.name
            file_content = read_file(file)
            files = {"image": (filename, file_content, "image/jpeg")}
        else:
            raise ValueError("Must provide url or file")

        # 1. 搜索
        resp = await self._send_request(
            method="post",
            params=params, # key 和 url 都在 params 中
            files=files
        )

        try:
            data = json.loads(resp.text)
        except Exception as e:
            logger.warning(f"[TraceMoe] JSON parse failed: {e}. Text: {resp.text}")
            return TraceMoeResponse(resp.text, resp.url)

        # 2. 获取元数据 (Anilist)
        # 收集所有 Anilist ID
        results = data.get("result", [])
        if results:
            seen_ids = set()
            for item in results:
                aid = item.get("anilist")
                if aid and aid not in seen_ids:
                    seen_ids.add(aid)
                    # 限制请求数，防止过多 (前3个通常够了)
                    if len(seen_ids) >= 3: 
                        break
            
            # 并发请求获取信息
            # 注意: self._send_request 是 async 的，这里简单循环 loop (或者 gather)
            # TraceMoe 的 GraphQL 似乎不支持批量 ID? query 是 ($id: Int) 单个
            
            # 使用简单的循环，可能会慢一点，但安全
            # 稍作优化: 缓存已获取的 info
            fetched_info = {}
            for aid in seen_ids:
                gql_resp = None
                try:
                    variables = {"id": aid}
                    gql_resp = await self._send_request(
                        method="post",
                        url=self.anilist_url,
                        json={"query": ANIME_INFO_QUERY, "variables": variables},
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        }
                    )
                    
                    try:
                        gql_data = json.loads(gql_resp.text)
                    except Exception as e:
                        logger.warning(f"[TraceMoe] Anilist JSON parse failed: {e}")
                        continue
                    
                    if "errors" in gql_data:
                        logger.warning(f"[TraceMoe] Anilist API returned errors for {aid}: {gql_data['errors']}")
                        # Trigger debug dump
                        raise Exception(f"API Error: {gql_data['errors']}")

                    media = gql_data.get("data", {}).get("Media")
                    if media:
                        logger.info(f"[TraceMoe] Successfully fetched info for {aid}: {media.get('title', {}).get('native', 'Unknown')}")
                        fetched_info[aid] = media
                    else:
                        logger.warning(f"[TraceMoe] Media data is empty for {aid}")

                except Exception as e:
                    logger.warning(f"[TraceMoe] Failed to fetch Anilist info for {aid}: {e}")
                    if gql_resp:
                        try:
                             save_dir = Path("data/plugins/img_rev_searcher/debug")
                             save_dir.mkdir(parents=True, exist_ok=True)
                             dump_path = save_dir / f"tracemoe_anilist_dump_{aid}_{int(time.time())}.json"
                             with open(dump_path, "w", encoding="utf-8") as f:
                                 f.write(gql_resp.text)
                             logger.info(f"[TraceMoe] Dumped Anilist debug JSON to: {dump_path.absolute()}")
                        except Exception:
                             pass
                    continue
            
            # 3. 注入信息到 data
            for item in results:
                aid = item.get("anilist")
                if aid in fetched_info:
                    item["_anime_info"] = fetched_info[aid]
        
        # 重新序列化为 JSON 供 Parser 使用
        new_resp_text = json.dumps(data)
        
        return TraceMoeResponse(new_resp_text, resp.url)
