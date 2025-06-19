@echo off
setlocal

:: =================================================================
:: ==            LANCEUR POUR LE SCRIPT D'INSTALLATION          ==
:: =================================================================
::
:: Ce script .bat sert uniquement a lancer le script PowerShell
:: 'setup.ps1' en s'assurant que les permissions sont correctes
:: pour son execution.
::

:: Titre de la fenetre de la console
title Lancement de l'installeur Chroma-GGUF

:: Message pour l'utilisateur
echo Lancement du script d'installation PowerShell...
echo Une nouvelle interface va s'afficher. Veuillez patienter.
echo.

:: Execution du script PowerShell
:: -NoProfile      : Ne charge pas le profil PowerShell de l'utilisateur (plus rapide et plus sûr).
:: -ExecutionPolicy Bypass : Autorise l'exécution de ce script sans changer la politique système.
:: -File "%~dp0src\setup.ps1" : Spécifie le chemin du script à exécuter.
::   -> "%~dp0" est une variable qui désigne le dossier où se trouve ce fichier .bat.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0src\setup.ps1"

echo.
echo Le script d'installation est termine.

endlocal