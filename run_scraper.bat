@echo off
echo ========================================
echo   Auction Tracker - Running Scrapers
echo ========================================
echo.

cd /d "c:\Users\david\Documents\Claude\Auction Tracker Opus"

echo [1/3] Running scrapers...
py master_scraper.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Scraper failed with exit code %ERRORLEVEL%
    pause
    exit /b 1
)

echo.
echo [2/3] Committing changes...
git add docs/data/auctions.json
git commit -m "Update auction data - %date% %time:~0,8%"

echo.
echo [3/3] Pushing to GitHub...
git push origin main

echo.
echo ========================================
echo   Done! GitHub Pages will update shortly.
echo ========================================
timeout /t 5
