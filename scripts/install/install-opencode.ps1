param([ValidateSet("Global", "Project")][string]$Scope = "Global", [string]$ProjectPath = (Get-Location).Path)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$defaultRef = ""
if ($env:PLUGIN_RELEASE_TAG) { $refValue = $env:PLUGIN_RELEASE_TAG } elseif ($defaultRef) { $refValue = $defaultRef } else { $refValue = "" }
$tmp = Join-Path ([IO.Path]::GetTempPath()) "agent-plugin-bootstrap-$([Guid]::NewGuid().ToString('N'))"
$archive = Join-Path $tmp "agent-plugin-bootstrap-opencode.zip"
$extract = Join-Path $tmp "dist"
if ($refValue) { $url = "https://github.com/fpiechowski/agent-plugin-bootstrap/releases/download/$refValue/agent-plugin-bootstrap-opencode.zip" } else { $url = "https://github.com/fpiechowski/agent-plugin-bootstrap/releases/latest/download/agent-plugin-bootstrap-opencode.zip" }
try { New-Item -ItemType Directory -Path $tmp | Out-Null; Invoke-WebRequest $url -OutFile $archive -UseBasicParsing; Expand-Archive -LiteralPath $archive -DestinationPath $extract; & (Join-Path $extract "install.ps1") -Scope $Scope -ProjectPath $ProjectPath } finally { if (Test-Path $tmp) { [IO.Directory]::Delete($tmp, $true) } }
