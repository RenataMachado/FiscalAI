@echo off
chcp 65001 >nul
setlocal EnableExtensions

rem ===================================================================
rem  ATUALIZAR.bat - instala uma versao nova do sistema, sem comandos.
rem
rem  1. Baixe o zip novo (nfe_app_ia_automatica_completo...zip) para Downloads
rem  2. Feche o VS Code e a janela do Streamlit
rem  3. De dois cliques neste arquivo
rem
rem  Nada e apagado: a versao atual vira uma pasta de backup ao lado.
rem ===================================================================

rem A pasta do projeto vai ser renomeada durante a atualizacao, entao este
rem arquivo se copia para a pasta temporaria e continua rodando de la.
if /i "%~1"=="--copia" goto principal
copy /y "%~f0" "%TEMP%\atualizar_nfe_app.bat" >nul
"%TEMP%\atualizar_nfe_app.bat" --copia "%~dp0"

:principal
title Atualizar o Sistema de Gestao de Notas Fiscais
set "ORIGEM=%~2"
cd /d "%USERPROFILE%"

rem Onde esta o projeto: a pasta deste arquivo (se ele estiver dentro do projeto)
rem ou Documentos\nfe_app_ia_automatica
set "PROJETO=%USERPROFILE%\Documents\nfe_app_ia_automatica"
if exist "%ORIGEM%app.py" set "PROJETO=%ORIGEM:~0,-1%"
for %%P in ("%PROJETO%") do set "PAI=%%~dpP"
for %%P in ("%PROJETO%") do set "NOME=%%~nxP"

rem O zip mais novo na pasta Downloads
set "ZIP="
for /f "delims=" %%F in ('dir /b /a-d /o-d "%USERPROFILE%\Downloads\nfe_app_ia_automatica_completo*.zip" 2^>nul') do (
    if not defined ZIP set "ZIP=%USERPROFILE%\Downloads\%%F"
)

echo.
echo ===================================================
echo   Atualizacao do Sistema de Gestao de Notas Fiscais
echo ===================================================
echo.
if not exist "%PROJETO%\.env" (
    echo [ERRO] Nao encontrei o projeto com o arquivo .env em:
    echo        %PROJETO%
    goto fim
)
if not defined ZIP (
    echo [ERRO] Nao encontrei o zip novo na pasta Downloads.
    echo        Baixe o arquivo nfe_app_ia_automatica_completo...zip e tente de novo.
    goto fim
)
echo Projeto atual: %PROJETO%
echo Versao nova:   %ZIP%
echo.
echo Antes de continuar, feche o VS Code e a janela do Streamlit.
echo.
pause

for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "CARIMBO=%%T"
set "BACKUP_NOME=%NOME%_backup_%CARIMBO%"
set "BACKUP=%PAI%%BACKUP_NOME%"
set "EXTRAIR=%PAI%_nfe_extraindo_%CARIMBO%"

echo.
echo [1/4] Guardando a versao atual como backup...
ren "%PROJETO%" "%BACKUP_NOME%" 2>nul
if not exist "%BACKUP%\.env" (
    echo [ERRO] Nao consegui renomear a pasta do projeto.
    echo        Feche o VS Code, a janela do Streamlit e as pastas do projeto abertas e tente de novo.
    goto fim
)

echo [2/4] Extraindo a versao nova...
mkdir "%EXTRAIR%" 2>nul
tar -xf "%ZIP%" -C "%EXTRAIR%"
move "%EXTRAIR%\nfe_app_ia_automatica" "%PROJETO%" >nul 2>nul
rd /s /q "%EXTRAIR%" 2>nul
if not exist "%PROJETO%\app.py" (
    echo [ERRO] Nao consegui extrair o zip. Voltando para a versao anterior...
    if exist "%PROJETO%" rd /s /q "%PROJETO%"
    ren "%BACKUP%" "%NOME%"
    goto fim
)

echo [3/4] Copiando o seu arquivo .env...
copy /y "%BACKUP%\.env" "%PROJETO%\.env" >nul

echo [4/4] Atualizando o banco de dados...
cd /d "%PROJETO%"
python scripts\setup_db.py
if errorlevel 1 (
    echo.
    echo [ATENCAO] A atualizacao do banco deu erro: veja a mensagem acima.
    echo           Os arquivos novos ja estao no lugar. O backup ficou em:
    echo           %BACKUP%
    goto fim
)

echo.
echo ===================================================
echo   Pronto! Sistema atualizado.
echo   Backup da versao anterior: %BACKUP%
echo ===================================================
echo.
choice /c SN /m "Quer abrir o sistema agora"
if errorlevel 2 goto fim
echo.
echo Abrindo o sistema no navegador. Para fechar o sistema, feche esta janela.
python -m streamlit run app.py

:fim
echo.
pause
endlocal
