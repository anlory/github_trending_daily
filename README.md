# GitHub Trending Daily

A mobile-friendly GitHub Trending viewer, built with Python + Flask.

## Features

- Scrape GitHub Trending repositories (name, description, language, stars, forks, today's gain)
- Dark theme card-style layout, mobile-first responsive design
- Daily / Weekly / Monthly time range switching
- Language filter (auto-extracts trending languages)
- Today's star gain badges (fire-graded: >=500 orange-red, >=100 gold, <100 green)
- Hover animation with gradient top border

## Setup

```bash
# Install dependencies (managed by uv)
uv sync
```

## Usage

### Web Server (interactive filtering)

```bash
uv run python app.py            # http://localhost:5000
uv run python app.py -p 8080    # custom port
```

### Static Export

```bash
uv run python app.py export                        # daily (default)
uv run python app.py export -s weekly              # weekly trending
uv run python app.py export -s monthly             # monthly trending
uv run python app.py export -l python -s monthly   # Python monthly
uv run python app.py export -o ./dist              # custom output dir
```

## Project Structure

```
├── pyproject.toml          # uv project config & dependencies
├── app.py                  # Entry point (Flask + CLI)
├── github_trending.py      # Scraper module
├── templates/
│   └── trending.html       # Mobile-first template
└── output/                 # Generated static HTML
```

## Dependencies

- [requests](https://pypi.org/project/requests/) - HTTP client
- [beautifulsoup4](https://pypi.org/project/beautifulsoup4/) - HTML parser
- [flask](https://pypi.org/project/flask/) - Web framework
