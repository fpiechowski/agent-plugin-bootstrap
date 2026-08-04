$ErrorActionPreference = "Stop"
$name = "agent-plugin-bootstrap"
$source = "fpiechowski/agent-plugin-bootstrap"
$defaultRef = ""
$pluginId = "agent-plugin-bootstrap@agent-plugin-bootstrap"
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) { throw "Codex CLI was not found on PATH." }
if ($env:PLUGIN_RELEASE_TAG) { $refValue = $env:PLUGIN_RELEASE_TAG } elseif ($defaultRef) { $refValue = $defaultRef } else { $refValue = "master" }
$marketplacesJson = & codex plugin marketplace list --json 2>$null
$marketplaces = if ($LASTEXITCODE -eq 0 -and $marketplacesJson) { $marketplacesJson | ConvertFrom-Json } else { $null }
if ($marketplaces.marketplaces.name -contains $name) { & codex plugin remove $pluginId 2>$null; & codex plugin marketplace remove $name 2>$null }
& codex plugin marketplace add $source --ref $refValue
if ($LASTEXITCODE -ne 0) { throw "Codex marketplace registration failed." }
& codex plugin add $pluginId
if ($LASTEXITCODE -ne 0) { throw "Codex plugin installation failed." }
Write-Host "agent-plugin-bootstrap is installed from $refValue. Start a new Codex conversation."
