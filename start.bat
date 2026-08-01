cd /d %~dp0
git pull
uv sync --upgrade
uv run main.py