param(
    [string]$TaskName = "SocialAutomation-Generation",
    [string]$Database = "data\sample_structure.db",
    [int]$Limit = 10,
    [int]$EveryMinutes = 15
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $Root "scripts\run_generation_scheduler.ps1"
if (-not (Test-Path $Runner)) { throw "Runner not found: $Runner" }

$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`" -Database `"$Database`" -Limit $Limit" -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes ([Math]::Max(1,$EveryMinutes)))
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Runs the Social Automation provider-aware generation queue." -Force
Write-Output "Installed task: $TaskName"
Write-Output "Runs every $EveryMinutes minutes."
