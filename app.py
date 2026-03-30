"""GitHub Trending Daily - 主入口

用法:
    python app.py                 # 启动 Web 服务 (localhost:5000)
    python app.py export          # 生成静态 HTML 文件到 output/
    python app.py export -l python -s weekly  # 指定语言和时间范围
"""

import argparse
import os
import re
import tempfile
from collections import Counter
from datetime import datetime

from flask import Flask, render_template, request

from github_trending import (
    fetch_trending,
    format_stars,
    get_available_languages,
    translate_descriptions,
)

app = Flask(__name__)

SINCE_OPTIONS = [
    {"value": "daily", "label": "Daily"},
    {"value": "weekly", "label": "Weekly"},
    {"value": "monthly", "label": "Monthly"},
]

SINCE_LABELS = {"daily": "今日趋势", "weekly": "本周趋势", "monthly": "本月趋势"}

# 语言颜色映射（补充 GitHub 页面未提供颜色的语言）
LANG_COLORS = {
    "python": "#3572A5",
    "javascript": "#f1e05a",
    "typescript": "#3178c6",
    "java": "#b07219",
    "go": "#00ADD8",
    "rust": "#dea584",
    "c++": "#f34b7d",
    "c": "#555555",
    "c#": "#178600",
    "ruby": "#701516",
    "php": "#4F5D95",
    "swift": "#F05138",
    "kotlin": "#A97BFF",
    "dart": "#00B4AB",
    "shell": "#89e051",
    "vue": "#41b883",
    "html": "#e34c26",
    "css": "#563d7c",
    "jupyter notebook": "#DA5B0B",
    "lua": "#000080",
    "zig": "#ec915c",
    "scala": "#c22d40",
    "r": "#198CE7",
    "perl": "#0298c3",
    "haskell": "#5e5086",
    "elixir": "#6e4a7e",
    "clojure": "#db5855",
    "objective-c": "#438eff",
}


def _get_top_languages(repos: list[dict], count: int = 8) -> list[dict]:
    """从仓库列表中提取最热门的编程语言。"""
    lang_counter = Counter()
    lang_color_map = {}
    for repo in repos:
        if repo["language"]:
            lang_counter[repo["language"]] += 1
            if repo["lang_color"]:
                lang_color_map[repo["language"]] = repo["lang_color"]

    top = lang_counter.most_common(count)
    result = []
    for name, _ in top:
        color = lang_color_map.get(name) or LANG_COLORS.get(name.lower(), "#8b949e")
        result.append({"name": name, "color": color})
    return result


# ========== Jinja2 自定义过滤器 ==========
@app.template_filter("format_stars")
def _jinja_format_stars(count: int) -> str:
    return format_stars(count)


@app.template_filter("regex_replace")
def _jinja_regex_replace(s: str, pattern: str, repl: str = "") -> str:
    return re.sub(pattern, repl, str(s))


# ========== Routes ==========
@app.route("/")
def index():
    language = request.args.get("language", "").strip() or None
    since = request.args.get("since", "daily")
    if since not in ("daily", "weekly", "monthly"):
        since = "daily"

    repos = fetch_trending(language=language, since=since)

    desc_lang = request.args.get("desc_lang", "zh")
    if desc_lang == "zh":
        repos = translate_descriptions(repos, target="zh-CN")

    top_languages = _get_top_languages(repos)

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %A")
    since_label = SINCE_LABELS.get(since, since)

    return render_template(
        "trending.html",
        repos=repos,
        language=language,
        since=since,
        since_label=since_label,
        since_options=SINCE_OPTIONS,
        date_str=date_str,
        top_languages=top_languages,
        desc_lang=desc_lang,
    )


# ========== CLI ==========
def export_static(language: str | None = None, since: str = "daily", output_dir: str = "output", desc_lang: str = "zh"):
    """导出为静态 HTML 文件。"""
    repos = fetch_trending(language=language, since=since)

    if desc_lang == "zh":
        repos = translate_descriptions(repos, target="zh-CN")

    top_languages = _get_top_languages(repos)

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %A")
    since_label = SINCE_LABELS.get(since, since)

    template = app.jinja_env.get_template("trending.html")
    html = template.render(
        repos=repos,
        language=language,
        since=since,
        since_label=since_label,
        since_options=SINCE_OPTIONS,
        date_str=date_str,
        top_languages=top_languages,
        desc_lang=desc_lang,
    )

    os.makedirs(output_dir, exist_ok=True)
    filename = f"trending_{since}"
    if language:
        filename += f"_{language}"
    filename += ".html"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"已生成: {filepath}  ({len(repos)} 个仓库)")
    return filepath


def screenshot(
    language: str | None = None,
    since: str = "daily",
    output_dir: str = "output",
    desc_lang: str = "zh",
    full_page: bool = False,
    width: int = 760,
):
    """生成页面截图为 PNG 文件。"""
    from playwright.sync_api import sync_playwright

    # 先导出静态 HTML
    html_path = export_static(
        language=language, since=since, output_dir=output_dir, desc_lang=desc_lang,
    )

    # 生成截图文件名
    os.makedirs(output_dir, exist_ok=True)
    png_name = os.path.splitext(os.path.basename(html_path))[0] + ".png"
    png_path = os.path.join(output_dir, png_name)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": width, "height": 800},
            device_scale_factor=2,
        )
        page.goto(f"file:///{html_path.replace(os.sep, '/')}", wait_until="networkidle")
        page.screenshot(path=png_path, full_page=full_page)
        browser.close()

    print(f"已生成截图: {png_path}")
    return png_path


def main():
    parser = argparse.ArgumentParser(description="GitHub Trending Daily")
    parser.add_argument("command", nargs="?", default="serve", help="serve | export | screenshot")
    parser.add_argument("-l", "--language", help="编程语言筛选")
    parser.add_argument("-s", "--since", default="daily", choices=["daily", "weekly", "monthly"], help="时间范围")
    parser.add_argument("-p", "--port", type=int, default=5000, help="Web 服务端口")
    parser.add_argument("-o", "--output", default="output", help="导出目录")
    parser.add_argument("--desc-lang", default="zh", choices=["zh", "en"], help="描述语言 (zh=中文, en=英文)")
    parser.add_argument("--full-page", action="store_true", help="截图包含完整页面")
    parser.add_argument("--width", type=int, default=760, help="截图视口宽度 (默认 760)")
    args = parser.parse_args()

    if args.command == "export":
        export_static(language=args.language, since=args.since, output_dir=args.output, desc_lang=args.desc_lang)
    elif args.command == "screenshot":
        screenshot(
            language=args.language, since=args.since, output_dir=args.output,
            desc_lang=args.desc_lang, full_page=args.full_page, width=args.width,
        )
    else:
        print(f"启动服务: http://localhost:{args.port}")
        app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
