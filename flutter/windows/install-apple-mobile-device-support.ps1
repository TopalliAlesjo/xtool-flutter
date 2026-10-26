# Install only Apple Mobile Device Support (the iPhone USB driver/service) from
# Apple's official iTunes for Windows installer, without installing iTunes.
#
#   powershell -ExecutionPolicy Bypass -File flutter\windows\install-apple-mobile-device-support.ps1 -Msi <path>
#
# Get <path> first: download iTunes64Setup.exe from https://www.apple.com/itunes/download/win64
# and extract AppleMobileDeviceSupport64.msi from it with 7-Zip (it is a plain archive):
#   7z e iTunes64Setup.exe AppleMobileDeviceSupport64.msi -o<folder>
#
# The script refuses to run unless the MSI carries a valid Authenticode signature
# from Apple Inc., refuses to touch an existing installation, and stops the service
# again if it ever listens on anything other than loopback. Windows will ask for
# administrator consent. No reboot is forced.
param(
    [Parameter(Mandatory = $true)][string]$Msi
)
$ErrorActionPreference = 'Stop'

$Msi = (Resolve-Path -LiteralPath $Msi).Path
$signature = Get-AuthenticodeSignature -LiteralPath $Msi
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Apple Inc\.') {
    throw "Not a valid Apple-signed package ($($signature.Status)); refusing to install."
}
'Signature: {0} — {1}' -f $signature.Status, $signature.SignerCertificate.Subject
'SHA256:    {0}' -f (Get-FileHash -Algorithm SHA256 -LiteralPath $Msi).Hash.ToLowerInvariant()

if (Get-Service -Name 'Apple Mobile Device Service' -ErrorAction SilentlyContinue) {
    'Apple Mobile Device Service is already installed; nothing to do.'
    return
}

$log = Join-Path ([IO.Path]::GetTempPath()) 'AppleMobileDeviceSupport-install.log'
$arguments = '/i "{0}" /qn /norestart /L*v "{1}"' -f $Msi, $log
$process = Start-Process -FilePath 'msiexec.exe' -ArgumentList $arguments -Verb RunAs -Wait -PassThru
if ($process.ExitCode -notin @(0, 3010)) { throw "msiexec failed with $($process.ExitCode); see $log" }

$service = Get-Service -Name 'Apple Mobile Device Service'
'Service: ' + $service.Status
$listeners = @(Get-NetTCPConnection -LocalPort 27015 -State Listen -ErrorAction SilentlyContinue)
if (@($listeners | Where-Object { $_.LocalAddress -notin @('127.0.0.1', '::1') }).Count) {
    Stop-Service -Name 'Apple Mobile Device Service'
    throw 'Service listened on a non-loopback address; stopped it.'
}
$listeners | Select-Object LocalAddress, LocalPort, State | Format-Table -AutoSize
