"""
轻量级网络搜索服务 - 基于 DuckDuckGo（免费，无需 API Key）
"""
try:
    from ddgs import DDGS
except ImportError:  # 可选依赖：未安装时搜索功能自动降级，不影响插件加载
    DDGS = None


class WebSearchService:
    """DuckDuckGo 免费搜索 + Jina Reader 网页读取"""

    READER_URL = "https://r.jina.ai"

    def search(self, query: str, max_results: int = 5) -> str:
        """搜索网络并返回结果摘要"""
        if DDGS is None:
            return "（未安装可选依赖 ddgs，网络搜索不可用）"
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

    @staticmethod
    def is_safe_public_url(url: str) -> bool:
        """只允许 http/https 且解析后为公网地址，避免 SSRF/内网探测。"""
        import ipaddress
        import socket
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
        except ValueError:
            return False
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        try:
            infos = socket.getaddrinfo(parsed.hostname, None)
        except OSError:
            return False
        for info in infos:
            try:
                ip = ipaddress.ip_address(info[4][0])
            except ValueError:
                return False
            if (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
                return False
        return True

    def read_page(self, url: str) -> str:
        """读取网页内容为纯文本（仅允许公网 http/https）"""
        if not self.is_safe_public_url(url):
            import logging
            logging.getLogger(__name__).warning("已拒绝非公网 URL: %s", url)
            return ""
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
