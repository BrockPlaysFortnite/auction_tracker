@echo off
echo ========================================
echo   Auction Tracker - Running Scrapers
echo ========================================
echo.

cd /d "c:\Users\david\Documents\Claude\Auction Tracker Opus"

echo [1/5] Running scrapers...
py master_scraper.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Scraper failed with exit code %ERRORLEVEL%
    pause
    exit /b 1
)

echo.
echo [2/5] Committing to GitHub Pages...
git add docs/data/auctions.json
git commit -m "Update auction data - %date% %time:~0,8%"

echo.
echo [3/5] Pushing to GitHub Pages...
git push origin main

echo.
echo [4/5] Committing to Sealcoat SAS website...
cd /d "c:\Users\david\Documents\Claude\SealcoatSAS Website\sealcoatsas-website"
git add public/data/auctions.json
git commit -m "Update auction data - %date% %time:~0,8%"

echo.
echo [5/5] Pushing to Cloudflare...
git push origin master

echo.
echo ========================================
echo   Done! Both sites will update shortly.
echo ========================================
timeout /t 5
