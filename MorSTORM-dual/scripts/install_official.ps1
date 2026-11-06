param([string]$TargetDir = '', [switch]$VerifyOnly, [switch]$Repair)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $TargetDir) { $TargetDir = Join-Path $projectRoot 'third_party' }
$TargetDir = [IO.Path]::GetFullPath($TargetDir)
$lock = Get-Content -LiteralPath (Join-Path $projectRoot 'shared/official_sources.lock.json') -Raw | ConvertFrom-Json
Add-Type -AssemblyName System.IO.Compression.FileSystem
foreach ($property in $lock.sources.PSObject.Properties) {
    $tool = $property.Name
    $spec = $property.Value
    $folder = Join-Path $TargetDir $tool
    $missing = @()
    foreach ($item in $spec.files) {
        $dest = Join-Path $folder $item.path
        if (Test-Path -LiteralPath $dest) {
            $actual = (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($actual -ne $item.sha256) {
                if (-not $Repair) { throw "Changed author source: $dest. Restore it or explicitly use -Repair." }
                $missing += $item
            }
        } else { $missing += $item }
    }
    if ($missing.Count -eq 0) { Write-Output "$tool verified: $($spec.revision)"; continue }
    if ($VerifyOnly) { throw "$tool author source missing or changed under $folder" }
    $cache = Join-Path $TargetDir '.downloads'
    New-Item -ItemType Directory -Force -Path $cache | Out-Null
    $zip = Join-Path $cache "$tool-$($spec.revision.Replace(':','-')).zip"
    if (-not (Test-Path -LiteralPath $zip)) {
        Write-Output "Downloading original $tool release $($spec.revision)"
        Invoke-WebRequest -Uri $spec.archive_url -OutFile $zip -TimeoutSec 600
    }
    if ($spec.archive_md5) {
        if ((Get-FileHash -LiteralPath $zip -Algorithm MD5).Hash.ToLowerInvariant() -ne $spec.archive_md5) {
            throw "Archive checksum mismatch: $zip"
        }
    }
    $archive = [IO.Compression.ZipFile]::OpenRead($zip)
    try {
        foreach ($item in $missing) {
            $entry = $archive.GetEntry($spec.archive_prefix + $item.path)
            if (-not $entry) { throw "Author archive entry missing: $($item.path)" }
            $dest = Join-Path $folder $item.path
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $dest, $true)
            if ((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.sha256) {
                throw "Author file checksum mismatch: $dest"
            }
        }
    } finally { $archive.Dispose() }
    Write-Output "$tool installed and verified: $($spec.revision)"
}
