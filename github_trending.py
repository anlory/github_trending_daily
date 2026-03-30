"""GitHub Trending 爬虫模块 - 抓取 GitHub Trending 页面数据"""

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime


GITHUB_TRENDING_URL = "https://github.com/trending"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_trending(
    language: str | None = None,
    since: str = "daily",
) -> list[dict]:
    """抓取 GitHub Trending 数据。

    Args:
        language: 编程语言筛选，如 'python'、'rust'，None 表示全部
        since: 时间范围 'daily' | 'weekly' | 'monthly'

    Returns:
        仓库信息列表
    """
    url = GITHUB_TRENDING_URL
    if language:
        url += f"/{language}"
    params = {"since": since}

    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = soup.select("article.Box-row")

    repos = []
    for article in articles:
        repo = _parse_article(article)
        if repo:
            repos.append(repo)

    return repos


def _parse_article(article) -> dict | None:
    """解析单个仓库 article 元素。"""
    try:
        # 仓库路径: /owner/repo
        h2 = article.select_one("h2 a")
        if not h2:
            return None
        href = h2["href"].strip("/")
        parts = href.split("/", 1)
        owner, name = parts[0], parts[1] if len(parts) > 1 else ""

        # 描述
        desc_el = article.select_one("p.col-9")
        description = desc_el.get_text(strip=True) if desc_el else ""

        # 编程语言
        lang_el = article.select_one("[itemprop='programmingLanguage']")
        language = lang_el.get_text(strip=True) if lang_el else ""

        # 语言颜色
        lang_color = ""
        lang_svg = article.select_one(".repo-language-color")
        if lang_svg and lang_svg.get("style"):
            match = re.search(r"background-color:\s*(#[0-9a-fA-F]{3,8})", lang_svg["style"])
            if match:
                lang_color = match.group(1)

        # Stars / Forks: <a href=".../stargazers">28,930</a>
        total_stars = _parse_link_count(article, "/stargazers")
        total_forks = _parse_link_count(article, "/forks")
        today_stars = _parse_today_stars(article)

        return {
            "owner": owner,
            "name": name,
            "full_name": href,
            "url": f"https://github.com/{href}",
            "description": description,
            "language": language,
            "lang_color": lang_color,
            "total_stars": total_stars,
            "total_forks": total_forks,
            "today_stars": today_stars,
        }
    except Exception:
        return None


def _parse_link_count(article, href_suffix: str) -> int:
    """根据链接 href 后缀提取数字（如 /stargazers, /forks）。"""
    for link in article.select("a[href$='" + href_suffix + "']"):
        text = link.get_text(strip=True)
        num = _parse_number(text)
        if num > 0:
            return num
    return 0


def _parse_today_stars(article) -> str:
    """提取今日新增 stars 文本（如 '+123'）。"""
    el = article.select_one(".d-inline-block.float-sm-right")
    if el:
        text = el.get_text(strip=True)
        # 格式: "1,234 stars today" 或 "★ 1,234"
        match = re.search(r"([\d,]+)\s*stars?\s*(today|this week|this month)", text, re.I)
        if match:
            return match.group(0).strip()
        # fallback: 直接返回数字部分
        match = re.search(r"([\d,]+)\s*★", text)
        if match:
            return f"+{match.group(1)} stars today"
    return ""


def _parse_number(text: str) -> int:
    """将 '1,234' 转换为 1234。"""
    text = text.replace(",", "").strip()
    try:
        return int(text)
    except ValueError:
        return 0


def get_available_languages() -> list[str]:
    """获取可用的编程语言列表。"""
    try:
        resp = requests.get(GITHUB_TRENDING_URL, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.select(".select-menu-list a")
        langs = []
        for link in links:
            href = link.get("href", "")
            match = re.search(r"/trending/([a-z0-9+#.-]+)$", href)
            if match:
                langs.append(match.group(1))
        return sorted(set(langs))
    except Exception:
        return []


def format_stars(count: int) -> str:
    """格式化 star 数量显示。"""
    if count >= 1000:
        return f"{count / 1000:.1f}k"
    return str(count)


def translate_descriptions(repos: list[dict], target: str = "zh-CN") -> list[dict]:
    """使用 GLM-4-Flash 批量翻译仓库描述。"""
    import json
    import os
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from openai import OpenAI

    api_key = os.environ.get("GLM_API_KEY", "")
    if not api_key:
        return repos

    items = [
        (i, repo["description"])
        for i, repo in enumerate(repos)
        if repo.get("description")
    ]

    if not items:
        return repos

    client = OpenAI(api_key=api_key, base_url="https://open.bigmodel.cn/api/paas/v4/")

    # Split into batches of 15 to stay within token limits
    batch_size = 15
    batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
    translated = {}

    def _translate_batch(batch: list[tuple[int, str]]) -> dict[int, str]:
        result = {}
        lines = "\n".join(f"{idx}: {desc}" for idx, desc in batch)
        prompt = (
            "你是一个专业的技术翻译。将以下 GitHub 仓库描述翻译为简体中文。"
            "保持技术术语准确性，翻译简洁自然。"
            "直接返回 JSON 对象，键为索引，值为翻译结果，不要其他内容。\n\n"
            f"{lines}"
        )
        try:
            resp = client.chat.completions.create(
                model="glm-4-flash",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            text = resp.choices[0].message.content.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                text = text.rsplit("```", 1)[0] if "```" in text else text
            mapping = json.loads(text)
            for idx, desc in batch:
                result[idx] = mapping.get(str(idx), mapping.get(idx, desc))
        except Exception:
            for idx, desc in batch:
                result[idx] = desc
        return result

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(_translate_batch, batch) for batch in batches]
        for future in as_completed(futures):
            translated.update(future.result())

    result = []
    for i, repo in enumerate(repos):
        repo_copy = dict(repo)
        if i in translated:
            repo_copy["description"] = translated[i]
        result.append(repo_copy)

    return result


if __name__ == "__main__":
    # 快速测试
    repos = fetch_trending(since="daily")
    print(f"获取到 {len(repos)} 个热门仓库\n")
    for repo in repos[:5]:
        print(f"  {repo['full_name']}  ⭐ {repo['today_stars']}")
        print(f"    {repo['description'][:80]}")
        print()
