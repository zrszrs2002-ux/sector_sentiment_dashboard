param(
    [string]$TaskName = "SectorSentimentRSSCollector",
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Argument = "-m src.news_collector"

try {
    $Action = New-ScheduledTaskAction -Execute $PythonExe -Argument $Argument -WorkingDirectory $ProjectRoot
    $Trigger = New-ScheduledTaskTrigger `
        -Once `
        -At ((Get-Date).AddMinutes(5)) `
        -RepetitionInterval (New-TimeSpan -Hours 4) `
        -RepetitionDuration (New-TimeSpan -Days 3650)
    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Description "Run RSS collector and incremental pipeline every 4 hours." `
        -Force | Out-Null

    Write-Host "Scheduled task registered: $TaskName"
    Write-Host "Working directory: $ProjectRoot"
    Write-Host "Command: $PythonExe $Argument"
    Write-Host "View task: Get-ScheduledTask -TaskName $TaskName"
    Write-Host "Delete task: Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
} catch {
    Write-Error "Failed to register scheduled task: $($_.Exception.Message)"
    exit 1
}
