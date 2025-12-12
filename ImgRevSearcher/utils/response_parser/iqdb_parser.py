from typing import Any, Dict, List
from pyquery import PyQuery

from .base_parser import BaseSearchResponse

class IqdbResponse(BaseSearchResponse):
    """
    IQDB 搜索结果解析类
    """
    def __init__(self, resp_data: str, resp_url: str, **kwargs: Any):
        super().__init__(resp_data, resp_url, **kwargs)


    def _parse_response(self, resp_data: str, **kwargs: Any) -> None:
        dom = PyQuery(resp_data)
        self.raw = []
        
        # 查找所有 .pages 下的 table (排除最外层布局 table)
        # HTML 结构: <div class='pages'><div><table>...</table></div></div>
        tables = dom(".pages table")
        
        for table in tables.items():
            # 检查是否为结果表格
            # 特征: 包含 "Best match" 或 "Additional match" 的 th
            header = table("th").text()
            if "match" not in header:
                continue
                
            result = self._parse_item(table)
            if result:
                self.raw.append(result)
        
        self.raw.sort(key=lambda x: x.get("similarity", 0), reverse=True)

    def _parse_item(self, table: PyQuery) -> Dict[str, Any]:
        try:
            # 1. 获取 URL 和 缩略图
            # <td class='image'><a href='...'><img src='...'></a></td>
            td_img = table("td.image")
            if not td_img:
                return None
                
            link_tag = td_img("a")
            if not link_tag:
                return None
                
            url = link_tag.attr("href")
            img_tag = link_tag("img")
            thumbnail = img_tag.attr("src")
            
            if not url:
                return None
                
            # 补全 URL
            if url.startswith("//"):
                url = "https:" + url
            elif url.startswith("/"):
                url = "https://iqdb.org" + url
            
            if thumbnail and thumbnail.startswith("/"):
                thumbnail = "https://iqdb.org" + thumbnail
                
            # 2. 获取相似度
            # 通常在某一行 <td>96% similarity</td>
            similarity = 0.0
            rows = table("tr")
            for tr in rows.items():
                text = tr.text()
                if "% similarity" in text:
                    try:
                        # "96% similarity"
                        sim_str = text.split("%")[0].strip().split()[-1] # 取最后一部分数字
                        similarity = float(sim_str)
                    except:
                        pass
            
            # 3. 其他信息 (尺寸, 评级, 来源)
            # 来源通常在第二行: <td><img src=icon>Danbooru ...</td>
            # 尺寸在后面: 1435x1011 [Safe]
            other_info = []
            
            # 尝试提取 source
            source_text = ""
            try:
                # 假设第二行是来源 (index 1)
                # table("tr").eq(1) 可能是图片行 (index 1 if header is 0)
                # Inspecting HTML:
                # tr0: th(Best match)
                # tr1: td.image
                # tr2: td(Source: Danbooru ...)
                # tr3: td(Size...)
                # tr4: td(Sim...)
                
                # Let's iterate and concat useful texts
                for tr in rows.items():
                    txt = tr.text().strip()
                    if "match" in txt: continue
                    if "% similarity" in txt: continue
                    if not txt: continue
                    if txt == table("th").text().strip(): continue
                    
                    # 避免重复图片链接文本
                    if not tr.find("td.image"): 
                        other_info.append(txt)
            except:
                pass

            return {
                "title": table("th").text() or "Result",
                "url": url,
                "thumbnail": thumbnail,
                "author": "",
                "similarity": similarity,
                "other_info": " | ".join(other_info)
            }
        except Exception:
            return None


    def show_result(self) -> str:
        if not self.raw:
            return "IQDB 未找到相关结果"
            
        return "\n".join([
            f"相似度: {item['similarity']}%\n"
            f"链接: {item['url']}\n"
            f"信息: {item['other_info']}\n"
            f"{'-'*30}"
            for item in self.raw[:3]
        ])
