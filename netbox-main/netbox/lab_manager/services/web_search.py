"""
轻量级网络搜索服务 - 基于 DuckDuckGo（免费，无需 API Key）
"""
from ddgs import DDGS


class WebSearchService:
    """DuckDuckGo 免费搜索 + Jina Reader 网页读取"""

    READER_URL = "https://r.jina.ai"

    def search(self, query: str, max_results: int = 5) -> str:
        """搜索网络并返回结果摘要"""
        try:
            results = list(DDGS().text(query, max_results=max_results))
            if not results:
                return ""
            lines = []
            for r in results:
                title = r.get("title", "")
                body = r.get("body", "")
                href = r.get("href", "")
                lines.append(f"- **{title}**\n  {body[:200]}\n  {href}")
            return "\n\n".join(lines)
        except Exception as e:
            return f"（搜索异常: {e}）"

    def read_page(self, url: str) -> str:
        """读取网页内容为纯文本"""
        try:
            import requests
            resp = requests.get(
                f"{self.READER_URL}/{url}",
                headers={"Accept": "text/plain"},
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.text[:3000]
            return ""
        except Exception:
            return ""

    def search_for_project(self, project_description: str) -> str:
        """搜索项目方案和硬件清单"""
        results = []
        queries = [
            f"{project_description} 所需硬件 BOM",
            f"{project_description} DIY 制作教程",
        ]
        for q in queries:
            result = self.search(q, max_results=2)
            if result and "搜索异常" not in result:
                results.append(f"### {q}\n{result}")
        return "\n\n".join(results) if results else ""
