param([ValidateSet("Global", "Project")][string]$Scope = "Global", [string]$ProjectPath = (Get-Location).Path)
$ErrorActionPreference = "Stop"
$sourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($Scope -eq "Global") { $configRoot = Join-Path $HOME ".config\opencode" } else { $configRoot = Join-Path (Resolve-Path $ProjectPath) ".opencode" }
New-Item -ItemType Directory -Force -Path $configRoot | Out-Null
foreach ($folder in @("skills", "commands", "plugins")) { $source = Join-Path $sourceRoot ".opencode\$folder"; $destination = Join-Path $configRoot $folder; if (Test-Path $source) { New-Item -ItemType Directory -Force -Path $destination | Out-Null; Get-ChildItem -Force $source | Copy-Item -Destination $destination -Recurse -Force } }
Write-Host "Installed agent-plugin-bootstrap 0.1.0 for OpenCode at $configRoot"
