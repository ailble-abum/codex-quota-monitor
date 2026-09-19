<#
.SYNOPSIS
    Optional per-user WinForms tray for the Codex quota monitor.

.DESCRIPTION
    Reads the monitor's numeric snapshot only.  The snapshot is one directory
    above this script (../snapshot.json) in the installed runtime.  It never
    starts or stops Codex.  Show and reset-position invoke the adapter helper.
#>

[CmdletBinding()]
param(
    [string]$RuntimeRoot = ''
)

$ErrorActionPreference = 'Stop'
$script:ScriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Definition
if ([string]::IsNullOrWhiteSpace($RuntimeRoot)) {
    $script:RuntimeRoot = [System.IO.Path]::GetFullPath((Join-Path $script:ScriptDirectory '..'))
} else {
    $script:RuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot)
}
$script:SnapshotPath = Join-Path $script:RuntimeRoot 'snapshot.json'
$script:HistoryPath = Join-Path $script:RuntimeRoot 'history.html'
$script:HistoryJsonPath = Join-Path $script:RuntimeRoot 'history.json'
$script:NotificationPath = Join-Path $script:RuntimeRoot 'notification.json'
$script:HelperPath = Join-Path $script:ScriptDirectory 'windows_monitor.py'
$script:StaleAfterSeconds = 120
$script:LastNotificationTimestamp = $null

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Get-Snapshot {
    if (-not (Test-Path -LiteralPath $script:SnapshotPath -PathType Leaf)) {
        return $null
    }
    try {
        $raw = Get-Content -LiteralPath $script:SnapshotPath -Raw -ErrorAction Stop
        if ([string]::IsNullOrWhiteSpace($raw)) {
            return $null
        }
        return ($raw | ConvertFrom-Json -ErrorAction Stop)
    } catch {
        return $null
    }
}

function Get-QuotaTimestamp {
    param([object]$Snapshot)
    if ($null -eq $Snapshot -or $null -eq $Snapshot.quota) {
        return $null
    }
    try {
        if ($null -ne $Snapshot.quota.updatedAt) {
            return [double]$Snapshot.quota.updatedAt
        }
    } catch {
        return $null
    }
    return $null
}

function Get-SnapshotTimestamp {
    param([object]$Snapshot)
    if ($null -eq $Snapshot) {
        return $null
    }
    try {
        if ($null -ne $Snapshot.at) {
            return [double]$Snapshot.at
        }
    } catch {
        return $null
    }
    return $null
}

function Test-QuotaStale {
    param([object]$Snapshot)
    $timestamp = Get-QuotaTimestamp -Snapshot $Snapshot
    if ($null -eq $timestamp) {
        return $true
    }
    $age = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - $timestamp
    return $age -ge $script:StaleAfterSeconds
}

function Test-SnapshotStale {
    param([object]$Snapshot)
    # Context is refreshed with the outer snapshot, independently of the
    # slower account quota read.
    $timestamp = Get-SnapshotTimestamp -Snapshot $Snapshot
    if ($null -eq $timestamp) {
        return $true
    }
    $age = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - $timestamp
    return $age -ge $script:StaleAfterSeconds
}

function Format-DurationLabel {
    param([object]$Minutes)
    if ($null -eq $Minutes) {
        return 'window'
    }
    try {
        $value = [double]$Minutes
    } catch {
        return 'window'
    }
    if ($value -le 0) {
        return 'window'
    }
    if (($value % 10080) -eq 0) {
        return ('{0}w' -f [int]($value / 10080))
    }
    if (($value % 1440) -eq 0) {
        return ('{0}d' -f [int]($value / 1440))
    }
    if (($value % 60) -eq 0) {
        return ('{0}h' -f [int]($value / 60))
    }
    return ('{0}m' -f [int]$value)
}

function Format-Remaining {
    param([object]$Remaining)
    try {
        return ('{0:0.#}%' -f [double]$Remaining)
    } catch {
        return '—'
    }
}

function Format-Reset {
    param([object]$UnixSeconds)
    try {
        if ($null -eq $UnixSeconds) {
            return ''
        }
        $local = [DateTimeOffset]::FromUnixTimeSeconds([long][double]$UnixSeconds).ToLocalTime()
        return (' · resets {0}' -f $local.ToString('g'))
    } catch {
        return ''
    }
}

function Get-QuotaLines {
    param([object]$Snapshot)
    if (Test-QuotaStale -Snapshot $Snapshot) {
        return @('Quota: stale (>120s)')
    }
    if ($null -eq $Snapshot -or $null -eq $Snapshot.quota -or $Snapshot.quota.status -ne 'live') {
        return @('Quota: unavailable')
    }
    $windows = @($Snapshot.quota.windows)
    if ($windows.Count -eq 0) {
        if ($Snapshot.quota.windowStatus -eq 'not_reported') {
            return @('Quota: not reported')
        }
        return @('Quota: unavailable')
    }
    $lines = @()
    foreach ($window in $windows) {
        # The label is derived from windowDurationMins, rather than primary /
        # secondary, so provider window changes remain visible in the tray.
        $label = Format-DurationLabel -Minutes $window.duration
        $lines += ('{0} quota: {1}{2}' -f $label, (Format-Remaining $window.remaining), (Format-Reset $window.resetsAt))
    }
    return $lines
}

function Get-ContextLine {
    param([object]$Snapshot)
    if (Test-SnapshotStale -Snapshot $Snapshot) {
        return 'Context: stale (>120s)'
    }
    if ($null -eq $Snapshot -or $null -eq $Snapshot.context) {
        return 'Context: unavailable'
    }
    $context = $Snapshot.context
    try {
        if ($null -ne $context.latest_context_percent) {
            $percent = '{0:0.#}%' -f [double]$context.latest_context_percent
            if ($null -ne $context.latest_context_tokens -and $null -ne $context.context_window) {
                return ('Context: {0} ({1}/{2})' -f $percent, $context.latest_context_tokens, $context.context_window)
            }
            return ('Context: {0}' -f $percent)
        }
    } catch {
        return 'Context: unavailable'
    }
    return 'Context: unavailable'
}

function Consume-Notification {
    if (-not (Test-Path -LiteralPath $script:NotificationPath -PathType Leaf)) {
        return
    }
    try {
        $raw = Get-Content -LiteralPath $script:NotificationPath -Raw -ErrorAction Stop
        $notification = $raw | ConvertFrom-Json -ErrorAction Stop
        $timestamp = [double]$notification.at
        $age = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - $timestamp
        if ($age -gt $script:StaleAfterSeconds) {
            return
        }
        if ([string]::IsNullOrWhiteSpace([string]$notification.message)) {
            return
        }
        # QuotaAlerts may leave the latest notification file in place.  The
        # in-memory timestamp makes this a once-per-timestamp consumer while
        # allowing a later quota event to replace it.
        if ($null -ne $script:LastNotificationTimestamp -and $timestamp -eq $script:LastNotificationTimestamp) {
            return
        }
        $script:LastNotificationTimestamp = $timestamp
        $script:NotifyIcon.ShowBalloonTip(5000, 'Codex quota monitor', [string]$notification.message, [System.Windows.Forms.ToolTipIcon]::Warning)
    } catch {
        return
    }
}

function Get-NotifyText {
    param([object]$Snapshot)
    $lines = @(Get-QuotaLines -Snapshot $Snapshot)
    $lines += Get-ContextLine -Snapshot $Snapshot
    $text = ($lines -join ' | ')
    # NotifyIcon.Text is limited to 63 characters on supported Windows builds.
    if ($text.Length -gt 63) {
        return $text.Substring(0, 60) + '...'
    }
    return $text
}

function Get-PythonExecutable {
    if (-not [string]::IsNullOrWhiteSpace($env:CODEX_MONITOR_PYTHON)) {
        return $env:CODEX_MONITOR_PYTHON
    }
    $python = Get-Command 'python.exe' -ErrorAction SilentlyContinue
    if ($null -ne $python) {
        return $python.Source
    }
    $launcher = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if ($null -ne $launcher) {
        return $launcher.Source
    }
    return $null
}

function Invoke-HelperAction {
    param([ValidateSet('show', 'reset-position')][string]$Action)
    $python = Get-PythonExecutable
    if ($null -eq $python -or -not (Test-Path -LiteralPath $script:HelperPath -PathType Leaf)) {
        $script:NotifyIcon.ShowBalloonTip(3000, 'Codex quota monitor', 'Python or the installed helper was not found.', [System.Windows.Forms.ToolTipIcon]::Warning)
        return
    }
    # Start-Process receives a quoted script argument so paths under
    # %LOCALAPPDATA% with spaces remain one argument.  The helper only talks
    # to the existing loopback renderer; it does not reopen Codex.
    $quotedHelper = '"' + $script:HelperPath.Replace('"', '\"') + '"'
    Start-Process -FilePath $python -ArgumentList @($quotedHelper, $Action) -WorkingDirectory $script:ScriptDirectory -WindowStyle Hidden | Out-Null
}

function Open-OwnedFile {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        Start-Process -FilePath $Path | Out-Null
        return
    }
    $script:NotifyIcon.ShowBalloonTip(3000, 'Codex quota monitor', 'The requested local file is not available yet.', [System.Windows.Forms.ToolTipIcon]::Info)
}

function New-TrayItem {
    param(
        [string]$Text,
        [scriptblock]$OnClick,
        [bool]$Enabled = $true
    )
    $item = New-Object System.Windows.Forms.ToolStripMenuItem
    $item.Text = $Text
    $item.Enabled = $Enabled
    if ($null -ne $OnClick) {
        $item.Add_Click($OnClick)
    }
    return $item
}

function Update-Tray {
    $snapshot = Get-Snapshot
    Consume-Notification
    $script:NotifyIcon.Text = Get-NotifyText -Snapshot $snapshot
    [void]$script:Menu.Items.Clear()

    [void]$script:Menu.Items.Add((New-TrayItem -Text 'Refresh' -OnClick { Update-Tray }))
    foreach ($line in @(Get-QuotaLines -Snapshot $snapshot)) {
        [void]$script:Menu.Items.Add((New-TrayItem -Text $line -Enabled $false))
    }
    [void]$script:Menu.Items.Add((New-TrayItem -Text (Get-ContextLine -Snapshot $snapshot) -Enabled $false))
    [void]$script:Menu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator))
    [void]$script:Menu.Items.Add((New-TrayItem -Text 'Open snapshot.json' -OnClick {
        Open-OwnedFile -Path $script:SnapshotPath
    }))
    [void]$script:Menu.Items.Add((New-TrayItem -Text 'Open history' -OnClick {
        $target = if (Test-Path -LiteralPath $script:HistoryPath -PathType Leaf) {
            $script:HistoryPath
        } else {
            $script:HistoryJsonPath
        }
        Open-OwnedFile -Path $target
    }))
    [void]$script:Menu.Items.Add((New-TrayItem -Text 'Show overlay' -OnClick {
        Invoke-HelperAction -Action 'show'
    }))
    [void]$script:Menu.Items.Add((New-TrayItem -Text 'Reset overlay position' -OnClick {
        Invoke-HelperAction -Action 'reset-position'
    }))
    [void]$script:Menu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator))
    [void]$script:Menu.Items.Add((New-TrayItem -Text 'Exit tray' -OnClick {
        $script:RefreshTimer.Stop()
        $script:NotifyIcon.Visible = $false
        $script:NotifyIcon.Dispose()
        $script:Menu.Dispose()
        [System.Windows.Forms.Application]::Exit()
    }))
}

$script:Menu = New-Object System.Windows.Forms.ContextMenuStrip
$script:NotifyIcon = New-Object System.Windows.Forms.NotifyIcon
$script:NotifyIcon.Icon = [System.Drawing.SystemIcons]::Application
$script:NotifyIcon.Visible = $true
$script:NotifyIcon.ContextMenuStrip = $script:Menu
$script:NotifyIcon.Add_DoubleClick({ Invoke-HelperAction -Action 'show' })

$script:RefreshTimer = New-Object System.Windows.Forms.Timer
$script:RefreshTimer.Interval = 10000
$script:RefreshTimer.Add_Tick({ Update-Tray })
$script:RefreshTimer.Start()
Update-Tray

[System.Windows.Forms.Application]::Run()
