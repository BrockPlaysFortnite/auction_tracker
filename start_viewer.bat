@echo off
echo Starting Auction Tracker Viewer...
echo.
echo Server will start at http://localhost:8000
echo Press Ctrl+C to stop the server when done
echo.

start http://localhost:8000/index.html
python -m http.server 8000