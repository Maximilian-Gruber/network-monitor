@echo off

echo removing network monitor services...

docker-compose down -v

echo =============================
echo network monitor services removed.
echo =============================