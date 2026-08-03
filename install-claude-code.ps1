$ErrorActionPreference = "Stop"
$name = "agent-plugin-bootstrap"
$source = "fpiechowski/agent-plugin-bootstrap"
$defaultRef = ""
$pluginId = "agent-plugin-bootstrap@agent-plugin-bootstrap"
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { throw "Claude Code CLI was not found on PATH." }
if ($env:PLUGIN_RELEASE_TAG) { $refValue = $env:PLUGIN_RELEASE_TAG } elseif ($defaultRef) { $refValue = $defaultRef } else { $refValue = "master" }
$marketplacesJson = & claude plugin marketplace list --json 2>$null
$marketplaces = if ($LASTEXITCODE -eq 0 -and $marketplacesJson) { $marketplacesJson | ConvertFrom-Json } else { $null }
if ($marketplaces.name -contains $name) { & claude plugin uninstall --scope user $pluginId 2>$null; & claude plugin marketplace remove $name 2>$null }
& claude plugin marketplace add --scope user "$source@$refValue"
if ($LASTEXITCODE -ne 0) { throw "Claude Code marketplace registration failed." }
& claude plugin install --scope user $pluginId
if ($LASTEXITCODE -ne 0) { throw "Claude Code plugin installation failed." }
Write-Host "agent-plugin-bootstrap is installed from $refValue. Restart Claude Code or run /reload-plugins."
