#set( $dollar = '$' )
#set( $hash = '#' )
${dollar}ErrorActionPreference = 'Stop'
& python (Join-Path ${dollar}PSScriptRoot 'local-preflight.py')
if (${dollar}LASTEXITCODE -ne 0) { throw 'Local preflight failed.' }
