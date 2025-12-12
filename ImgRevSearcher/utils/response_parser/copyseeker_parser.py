from typing import Any, Optional, Union
from typing_extensions import override
from .base_parser import BaseResParser, BaseSearchResponse


class CopyseekerItem(BaseResParser):
    """
    Copyseeker搜索结果项解析器
    
    解析单个匹配结果，提取URL、标题和缩略图等信息
    """
    
    def __init__(self, data: dict[str, Any], **kwargs: Any):
        """
        初始化Copyseeker结果项解析器
        
        参数:
            data: 原始结果数据
            **kwargs: 其他解析参数
        """
        super().__init__(data, **kwargs)

    @override
    def _parse_data(self, data: Union[str, dict[str, Any]], **kwargs: Any) -> None:
        """
        解析Copyseeker结果数据 (RapidAPI)
        """
        if isinstance(data, str):
            # VisuallySimilar only provides URL string
            self.url = data
            self.title = "Visually Similar Image"
            self.thumbnail = data
            self.website_rank = 0.0
        else:
            # Pages or standard items - Handle PascalCase (RapidAPI) and lowercase fallback
            self.url = data.get("Url") or data.get("url", "")
            self.title = data.get("Title") or data.get("title", "")
            
            # Thumbnail handling: MatchingImages (list of str) or mainImage or thumbnail
            matching_images = data.get("MatchingImages") or data.get("matchingImages")
            if matching_images and isinstance(matching_images, list) and len(matching_images) > 0:
                self.thumbnail = matching_images[0]
            else:
                self.thumbnail = data.get("thumbnail") or data.get("mainImage", "")
            
            rank = data.get("Rank") or data.get("rank", 0.0)
            try:
                self.website_rank = float(rank)
            except (ValueError, TypeError):
                self.website_rank = 0.0


class CopyseekerResponse(BaseSearchResponse[CopyseekerItem]):
    """
    Copyseeker搜索响应解析器
    
    解析完整的Copyseeker API响应，包含匹配结果、相似图片和EXIF信息等
    """
    
    def __init__(self, resp_data: dict[str, Any], resp_url: str, **kwargs: Any) -> None:
        """
        初始化Copyseeker响应解析器
        
        参数:
            resp_data: 原始响应数据
            resp_url: 响应URL
            **kwargs: 其他解析参数
        """
        super().__init__(resp_data, resp_url, **kwargs)

    @override
    def _parse_response(self, resp_data: dict[str, Any], **kwargs: Any) -> list[CopyseekerItem]:
        items: list[CopyseekerItem] = []
        
        # 1. Best Guess
        best_guess = resp_data.get("BestGuessLabel")
        if best_guess:
            items.append(CopyseekerItem({
                "title": f"Best Guess: {best_guess}",
                "url": "",
                "rank": 100.0,
                "mainImage": ""
            }))

        # 2. Pages (Web Results)
        # Assuming list of dicts based on Google Lens generic structure
        pages = resp_data.get("Pages", [])
        if pages and isinstance(pages, list):
            for page in pages:
                if isinstance(page, dict):
                    items.append(CopyseekerItem(page))

        # 3. Visually Similar (Images)
        # List of strings (URLs)
        similar = resp_data.get("VisuallySimilar", [])
        if similar and isinstance(similar, list):
            for img_url in similar:
                if isinstance(img_url, str) and img_url.startswith("http"):
                    items.append(CopyseekerItem(img_url))

        # Populate attributes required by show_result
        self.raw = items
        # self.similar_image_urls expects list of strings
        self.similar_image_urls = [i.thumbnail for i in items if i.title == "Visually Similar Image"]

        return items

    @override
    def show_result(self) -> Optional[str]:
        """
        生成可读的搜索结果文本
        """
        if not self.raw and not self.similar_image_urls:
            # Need to populate raw/similar logic in _parse_response or re-derive here
            # Since items are returned by _parse_response but NOT stored in self.raw explicitly in the new loop?
            # Wait, BaseSearchResponse usually doesn't store items automatically?
            # BaseSearchResponse usually assumes `_parse_response` parses things.
            # But where does it store them? The BaseSearchResponse doesn't store the return value of _parse_response?
            # Let's check BaseSearchResponse logic separately.
            # For now, I'll rely on what I put in `_parse_response`.
            # Actually, the base class typically calls `self.items = self._parse_response(...)`?
            # I need to verify BaseSearchResponse behavior.
            pass
        
        # Re-derive for display since I didn't store them in self in the previous step (I returned them)
        # Or better: Update _parse_response to store them in self.raw/similar for use here.
        
        lines = []
        
        # Filter items
        pages = [i for i in self.raw if i.title != "Visually Similar Image" and "Best Guess" not in i.title]
        guesses = [i for i in self.raw if "Best Guess" in i.title]
        similar = [i for i in self.raw if i.title == "Visually Similar Image"]
        
        if guesses:
            lines.append(f"🔍 {guesses[0].title}")
            
        if pages:
            lines.append(f"🔗 最佳匹配: {pages[0].url}")
            if pages[0].title:
                lines.append(f"📄 标题: {pages[0].title}")
        else:
            lines.append("⚠️ 未找到精确网页匹配")
            
        if similar:
            lines.append(f"\n🖼️ 相似图片 ({len(similar)} 张):")
            for i, item in enumerate(similar[:5], 1):
                lines.append(f"{i}. {item.url}")
                
        return "\n".join(lines) if lines else None
