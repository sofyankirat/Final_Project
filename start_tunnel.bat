@echo off
echo ==============================================================
echo Smart Attendance System - Public Internet Tunnel Starter
echo ==============================================================
echo.
echo Starting the tunnel to expose port 7860 to the internet...
echo Please copy the wss:// URL generated below and give it to your teammate.
echo Keep this window open while the camera is streaming!
echo.
ssh -o StrictHostKeyChecking=no -R 80:127.0.0.1:7860 nokey@localhost.run
pause
