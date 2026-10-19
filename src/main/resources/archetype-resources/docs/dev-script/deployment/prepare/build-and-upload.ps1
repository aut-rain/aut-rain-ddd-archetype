#set( $dollar = '$' )
#set( $hash = '#' )
[CmdletBinding()]
param(
    [string]${dollar}Server = '',
    [int]${dollar}SshPort = 22,
    [string]${dollar}RemoteDir = '${artifactId}-incoming',
    [switch]${dollar}BuildOnly,
    [switch]${dollar}UploadOnly,
    [switch]${dollar}ToolsOnly,
    [string]${dollar}Package = '',
    [ValidateSet('full', 'frontend', 'backend')][string]${dollar}Component = 'full',
    [string]${dollar}BasePackage = ''
)
${dollar}ErrorActionPreference = 'Stop'
${dollar}python = (Get-Command python -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
${dollar}arguments = @((Join-Path ${dollar}PSScriptRoot 'build_upload.py'), '--ssh-port', "${dollar}SshPort", '--remote-dir', ${dollar}RemoteDir)
if (${dollar}Server) { ${dollar}arguments += @('--server', ${dollar}Server) }
if (${dollar}BuildOnly) { ${dollar}arguments += '--build-only' }
if (${dollar}UploadOnly) { ${dollar}arguments += '--upload-only' }
if (${dollar}ToolsOnly) { ${dollar}arguments += '--tools-only' }
if (${dollar}Package) { ${dollar}arguments += @('--package', ${dollar}Package) }
${dollar}arguments += @('--component', ${dollar}Component)
if (${dollar}BasePackage) { ${dollar}arguments += @('--base-package', ${dollar}BasePackage) }
& ${dollar}python @arguments
if (${dollar}LASTEXITCODE -ne 0) { throw "Delivery failed (exit ${dollar}LASTEXITCODE)." }
