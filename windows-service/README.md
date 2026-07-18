# Windows service

The precompiled Windows binary is a console application. To run it durably in
the background, use [WinSW](https://github.com/winsw/winsw) as a small service
wrapper.

This directory contains:

- `install-windows-service.ps1`: installs, starts, stops, or uninstalls the
  Windows service.
- `winsw/FlareSolverr.xml`: WinSW service configuration template.

## Install

Run PowerShell as Administrator from the repository root or from this directory:

```powershell
.\windows-service\install-windows-service.ps1 `
  -FlareSolverrPath "C:\Program Files\FlareSolverr\flaresolverr.exe" `
  -ServiceDirectory "C:\Program Files\FlareSolverr"
```

The installer downloads WinSW when it is not already present, writes the service
configuration, installs the service, and starts it.

## Configure

FlareSolverr environment variables can be passed as a hashtable:

```powershell
.\windows-service\install-windows-service.ps1 `
  -FlareSolverrPath "C:\Program Files\FlareSolverr\flaresolverr.exe" `
  -Environment @{
    LOG_LEVEL = "info"
    HOST = "0.0.0.0"
    PORT = "8191"
    CAPTCHA_SOLVER = "none"
  }
```

Do not expose FlareSolverr to the internet. Bind to `127.0.0.1` unless other
machines on a trusted private network need to reach it.

## Verify

```powershell
Get-Service FlareSolverr
Invoke-RestMethod "http://127.0.0.1:8191/"
```

Service logs are written under the service directory by WinSW:

```text
C:\Program Files\FlareSolverr\logs\
```

## Uninstall

```powershell
.\windows-service\install-windows-service.ps1 -Uninstall
```
