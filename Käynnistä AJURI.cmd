@echo off
title AJURI kaynnistys
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\kaynnista.ps1" %*
