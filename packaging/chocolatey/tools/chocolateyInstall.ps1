$ErrorActionPreference = 'Stop'

$packageArgs = @{
  packageName    = 'openagent'
  fileType       = 'exe'
  url64bit       = 'https://github.com/haseeb-heaven/open-agent/releases/download/v<VERSION>/openagent-win-x64.exe'
  checksum64     = '<SHA256>'
  checksumType64 = 'sha256'
  silentArgs     = '/S'
}

Install-ChocolateyPackage @packageArgs
