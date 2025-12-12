import json
from typing import Any, Dict, List
from typing_extensions import override
from .base_parser import BaseSearchResponse

class TraceMoeResponse(BaseSearchResponse):
    """
    TraceMoe 搜索结果解析类
    """
    def __init__(self, resp_data: str, resp_url: str, **kwargs: Any):
        super().__init__(resp_data, resp_url, **kwargs)

    @override
    def _parse_response(self, resp_data: str, **kwargs: Any) -> None:
        try:
            data = json.loads(resp_data)
            self.raw = []
            
            error = data.get("error", "")
            if error:
                return

            results = data.get("result", [])
            for item in results:
                # 提取基本信息
                similarity = item.get("similarity", 0)
                episode = item.get("episode", "?")
                timestamp = item.get("from", 0)
                
                # 格式化时间戳 (seconds -> mm:ss)
                m, s = divmod(int(timestamp), 60)
                time_str = f"{m:02d}:{s:02d}"
                
                # 获取 metadata (由 Request 层注入的 _anime_info)
                anime_info = item.get("_anime_info", {})
                title_native = anime_info.get("title", {}).get("native", "")
                title_romaji = anime_info.get("title", {}).get("romaji", "")
                title_english = anime_info.get("title", {}).get("english", "")
                
                # 优先显示 native > romaji > english (或者全部显示)
                title_display = title_native or title_romaji or title_english or "Unknown Anime"
                
                img_url = item.get("image", "")
                video_url = item.get("video", "")
                
                self.raw.append({
                    "title": title_display,
                    "similarity": f"{similarity*100:.1f}",
                    "episode": episode,
                    "time": time_str,
                    "thumbnail": img_url,
                    "video": video_url,
                    "url": video_url, # 使用视频链接作为主要跳转
                    "other_info": f"Ep {episode} @ {time_str}",
                    "author": "", # 动画没有单一作者
                })
                
        except json.JSONDecodeError:
            pass

    @override
    def show_result(self) -> str:
        if not self.raw:
            return "TraceMoe 未找到相关结果"
            
        return "\n".join([
            f"番名: {item['title']}\n"
            f"集数: {item['episode']} (时间点: {item['time']})\n"
            f"相似度: {item['similarity']}%\n"
            f"预览: {item['video']}\n"
            f"{'-'*30}"
            for item in self.raw[:3]
        ])
