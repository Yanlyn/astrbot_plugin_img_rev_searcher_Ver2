from typing import Any, List, Dict
from pyquery import PyQuery
from typing_extensions import override
from .base_parser import BaseSearchResponse

BASE_URL = "https://ascii2d.net"

class Ascii2DResponse(BaseSearchResponse):
    """
    Ascii2D 搜索结果解析类
    """
    def __init__(self, resp_data: str, resp_url: str, **kwargs: Any):
        super().__init__(resp_data, resp_url, **kwargs)

    @override
    def _parse_response(self, resp_data: str, **kwargs: Any) -> None:
        dom = PyQuery(resp_data)
        self.raw = []
        
        # ASCII2D 结果通常在 .item-box 中
        # 第一个是上传的图片，通常跳过 (但有时需要校验)
        items = dom("div.row.item-box")
        
        for item in items.items():
            # 忽略没有详情链接的项（通常是自身的缩略图）
            if not item.find("div.detail-box a"):
                continue
                
            result = self._parse_item(item)
            if result:
                self.raw.append(result)

    def _parse_item(self, item: PyQuery) -> Dict[str, Any]:
        try:
            # 提取图片哈希 (hash)
            hash_txt = item.find("div.hash").text()
            
            # 提取详情信息 (分辨率，大小等)
            params = item.find("div.text-muted").text() # e.g. 1000x1000 png 100kb
            
            # 缩略图
            img_src = item.find("img").attr("src")
            if img_src and img_src.startswith("/"):
                img_src = f"{BASE_URL}{img_src}"
                
            # 提取外部链接 (pixiv, twitter 等)
            detail_box = item.find("div.detail-box")
            links = detail_box.find("a")
            
            title = ""
            url = ""
            author = ""
            author_url = ""
            
            if links:
                # 第一个链接通常是作品链接
                first_link = links.eq(0)
                title = first_link.text() or "No Title"
                url = first_link.attr("href")
                
                # 第二个链接通常是作者
                if len(links) > 1:
                    second_link = links.eq(1)
                    author = second_link.text()
                    author_url = second_link.attr("href")
            
            return {
                "title": title,
                "url": url,
                "author": author,
                "author_url": author_url,
                "thumbnail": img_src,
                "other_info": f"{hash_txt} {params}"
            }
        except Exception:
            return None

    @override
    def show_result(self) -> str:
        if not self.raw:
            return "ASCII2D 未找到相关结果"
            
        return "\n".join([
            f"标题: {item['title']}\n"
            f"作者: {item['author']}\n"
            f"链接: {item['url']}\n"
            f"信息: {item['other_info']}\n"
            f"{'-'*30}"
            for item in self.raw[:3] # 默认只展示前3个文本
        ])
