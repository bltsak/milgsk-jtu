$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
Push-Location $PSScriptRoot
try {
    python -m PyInstaller --noconfirm --clean --onefile --windowed --name Fig --icon "$PSScriptRoot/assets/fig.ico" --add-data "$PSScriptRoot/assets;assets" --exclude-module PyQt6 --exclude-module PyQt5 --exclude-module tkinter --distpath dist --workpath build --specpath build "$PSScriptRoot/fig_pet.py"
} finally {
    Pop-Location
}
