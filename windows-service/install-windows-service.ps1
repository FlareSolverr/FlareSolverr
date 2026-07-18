[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$ServiceName = "FlareSolverr",
    [string]$DisplayName = "FlareSolverr",
    [string]$Description = "FlareSolverr proxy service",
    [string]$ServiceDirectory = "C:\Program Files\FlareSolverr",
    [string]$FlareSolverrPath = "C:\Program Files\FlareSolverr\flaresolverr.exe",
    [string]$WinSWVersion = "2.12.0",
    [string]$WinSWWrapperName = "FlareSolverrService",
    [hashtable]$Environment = @{
        LOG_LEVEL = "info"
        HOST = "127.0.0.1"
        PORT = "8191"
        CAPTCHA_SOLVER = "none"
    },
    [switch]$Uninstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    $adminRole = [Security.Principal.WindowsBuiltInRole]::Administrator
    if (-not $principal.IsInRole($adminRole)) {
        throw "Run this script from an elevated PowerShell session."
    }
}

function ConvertTo-XmlText {
    param([string]$Value)
    return [Security.SecurityElement]::Escape($Value)
}

function Get-WinSWDownloadUrl {
    param([string]$Version)
    return "https://github.com/winsw/winsw/releases/download/v$Version/WinSW-x64.exe"
}

Assert-Administrator

$serviceExe = Join-Path $ServiceDirectory "$WinSWWrapperName.exe"
$serviceXml = Join-Path $ServiceDirectory "$WinSWWrapperName.xml"

$serviceExeFullPath = [IO.Path]::GetFullPath($serviceExe)
$flareSolverrFullPath = [IO.Path]::GetFullPath($FlareSolverrPath)
if ($serviceExeFullPath.Equals($flareSolverrFullPath, [StringComparison]::OrdinalIgnoreCase)) {
    throw "WinSW wrapper path must be different from the FlareSolverr executable path."
}

if ($Uninstall) {
    $existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($existing) {
        if ($existing.Status -ne "Stopped") {
            if ($PSCmdlet.ShouldProcess($ServiceName, "stop service")) {
                Stop-Service -Name $ServiceName -Force -ErrorAction Stop
            }
        }
        if (Test-Path $serviceExe) {
            if ($PSCmdlet.ShouldProcess($ServiceName, "uninstall service")) {
                & $serviceExe uninstall
            }
        } else {
            throw "Cannot uninstall because $serviceExe was not found."
        }
    }
    return
}

if (-not (Test-Path $FlareSolverrPath)) {
    throw "FlareSolverr executable not found: $FlareSolverrPath"
}

if (-not (Test-Path $ServiceDirectory)) {
    if ($PSCmdlet.ShouldProcess($ServiceDirectory, "create service directory")) {
        New-Item -ItemType Directory -Path $ServiceDirectory -Force | Out-Null
    }
}

if (-not (Test-Path $serviceExe)) {
    $url = Get-WinSWDownloadUrl -Version $WinSWVersion
    if ($PSCmdlet.ShouldProcess($serviceExe, "download WinSW $WinSWVersion")) {
        Invoke-WebRequest -Uri $url -OutFile $serviceExe
    }
}

$envEntries = foreach ($item in $Environment.GetEnumerator() | Sort-Object Name) {
    '    <env name="{0}" value="{1}" />' -f (ConvertTo-XmlText $item.Name), (ConvertTo-XmlText ([string]$item.Value))
}

$xml = @"
<service>
  <id>$(ConvertTo-XmlText $ServiceName)</id>
  <name>$(ConvertTo-XmlText $DisplayName)</name>
  <description>$(ConvertTo-XmlText $Description)</description>
  <executable>$(ConvertTo-XmlText $FlareSolverrPath)</executable>
  <workingdirectory>$(ConvertTo-XmlText (Split-Path -Parent $FlareSolverrPath))</workingdirectory>
  <startmode>Automatic</startmode>
  <onfailure action="restart" delay="5 sec" />
  <resetfailure>1 hour</resetfailure>
  <log mode="roll-by-size-time">
    <sizeThreshold>10485760</sizeThreshold>
    <pattern>yyyyMMdd</pattern>
    <keepFiles>8</keepFiles>
  </log>
$($envEntries -join [Environment]::NewLine)
</service>
"@

if ($PSCmdlet.ShouldProcess($serviceXml, "write WinSW service configuration")) {
    Set-Content -Path $serviceXml -Value $xml -Encoding UTF8
}

$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $existingService) {
    if ($PSCmdlet.ShouldProcess($ServiceName, "install service")) {
        & $serviceExe install
    }
} else {
    if ($existingService.Status -ne "Stopped") {
        if ($PSCmdlet.ShouldProcess($ServiceName, "restart service")) {
            Restart-Service -Name $ServiceName -Force
        }
    }
}

if ($PSCmdlet.ShouldProcess($ServiceName, "start service")) {
    Start-Service -Name $ServiceName
}

Get-Service -Name $ServiceName
