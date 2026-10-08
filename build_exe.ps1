# Build the Windows executable with the bundled application icon.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path "ZaraExImport.ico")) {
    throw "Missing ZaraExImport.ico. Run git pull origin main first."
}

python -m pip install --upgrade pyinstaller "Pillow>=10"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller installation failed." }

python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

# Enlarge the artwork within the ICO canvas before attaching it to the EXE.
python optimize_icon.py
if ($LASTEXITCODE -ne 0) { throw "Icon optimization failed." }
$iconPath = Join-Path $PSScriptRoot ".build_assets\ZaraExImport.ico"

python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name "ZaraExImport" `
    --icon "$iconPath" `
    --add-data "$iconPath;." `
    --add-data "zaraex_template.xls;." `
    --add-data "products.json;." `
    --add-data "locations.json;." `
    --add-data "city_municipalities.json;." `
    main.py
if ($LASTEXITCODE -ne 0) { throw "Windows executable build failed." }

Write-Host "Ready: $PSScriptRoot\dist\ZaraExImport.exe"
