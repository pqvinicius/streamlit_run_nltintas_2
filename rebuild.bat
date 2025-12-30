@echo off
echo ==========================================
echo REBUILIDING RANKING VENDEDORES BOT
echo ==========================================
echo.
echo [1/3] Limpando pastas antigas...
if exist build rd /s /q build
if exist dist rd /s /q dist

echo [2/3] Gerando novo executavel...
pyinstaller ranking_vendedores.spec --noconfirm

echo [3/3] Concluido! 
echo O novo executavel esta em dist\RankingVendedoresBot\
echo.
pause
