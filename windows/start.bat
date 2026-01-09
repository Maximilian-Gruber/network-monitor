@echo off
echo ==============================
echo  Network Monitor Setup
echo ==============================

docker compose run --rm -it setup
docker compose up -d --build

echo.
echo Dashboard running at:
echo http://localhost:8050
start http://localhost:8050

pause
