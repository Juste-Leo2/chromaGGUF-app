@echo off
setlocal

:: =================================================================
:: ==            INSTALLATION TASK EXECUTOR                     ==
:: =================================================================
::
:: This script executes a single installation step based on the
:: argument it receives (%1). It is called by setup.ps1.
:: It ensures every command runs inside the activated Conda env.
::

:: --- Get the step number to execute ---
set "STEP_TO_RUN=%1"
if not defined STEP_TO_RUN (
    echo [ERREUR] This script must be called with a step number.
    exit /b 1
)

:: --- Paths ---
set "MINICONDA_PATH=%~dp0..\miniconda"
set "MODELS_PATH=%~dp0..\models"

:: --- Activate Conda Environment ---
:: This MUST be done before any other step.
call "%MINICONDA_PATH%\Scripts\activate.bat" "%MINICONDA_PATH%"
if %errorlevel% neq 0 (
    echo [ERREUR] Failed to activate the Conda environment.
    exit /b 1
)

:: --- JUMP to the requested step ---
goto STEP_%STEP_TO_RUN%


:STEP_1
echo --- Running Step 1/6: Installing Python...
call conda install -y -c conda-forge python=3.10 ca-certificates certifi openssl
if %errorlevel% neq 0 ( echo [ERREUR] Python installation failed. & exit /b 1 )
goto END

:STEP_2
echo --- Running Step 2/6: Installing CUDA libraries...
call conda install -y -c nvidia/label/cuda-12.4.0 cuda
if %errorlevel% neq 0 ( echo [ERREUR] CUDA installation failed. & exit /b 1 )
goto END

:STEP_3
echo --- Running Step 3/6: Installing 'uv' and dependencies...
call pip install uv
call uv pip install -r "%~dp0..\requirements.txt" --system
if %errorlevel% neq 0 ( echo [ERREUR] Failed to install dependencies from requirements.txt. & exit /b 1 )
goto END

:STEP_4
echo --- Running Step 4/6: Installing PyTorch...
call uv pip install torch torchvision torchaudio --system --extra-index-url https://download.pytorch.org/whl/cu124 --reinstall
if %errorlevel% neq 0 ( echo [ERREUR] PyTorch installation failed. & exit /b 1 )
goto END

:STEP_5
echo --- Running Step 5/6: Verifying PyTorch + CUDA integration...
call python -c "import torch; assert torch.cuda.is_available(), 'PyTorch cannot see CUDA.'"
if %errorlevel% neq 0 (
    echo [ERREUR] CRITICAL TEST FAILED: PyTorch cannot communicate with the GPU.
    echo Verify your NVIDIA drivers are up-to-date and compatible with CUDA 12.4.
    exit /b 1
)
echo PyTorch and CUDA are communicating successfully!
goto END

:STEP_6
echo --- Running Step 6/6: Downloading models...
call uv pip install huggingface-hub --system
call huggingface-cli download --quiet silveroxides/Chroma-GGUF chroma-unlocked-v37/chroma-unlocked-v37-Q4_0.gguf --local-dir "%MODELS_PATH%" --local-dir-use-symlinks False
call huggingface-cli download --quiet city96/t5-v1_1-xxl-encoder-gguf t5-v1_1-xxl-encoder-Q4_K_M.gguf --local-dir "%MODELS_PATH%" --local-dir-use-symlinks False
call huggingface-cli download --quiet lodestones/Chroma ae.safetensors --local-dir "%MODELS_PATH%" --local-dir-use-symlinks False
if %errorlevel% neq 0 ( echo [ERREUR] A model download failed. & exit /b 1 )
goto END


:UNKNOWN_STEP
echo [ERREUR] Unknown step number provided: %STEP_TO_RUN%
exit /b 1

:END
exit /b 0