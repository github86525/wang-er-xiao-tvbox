param(
    [Parameter(Mandatory = $true)]
    [string]$RawBaseUrl,
    [string]$InputJson = "",
    [string]$OutputJson = ""
)

function Convert-RelativePathsToOnline {
    param(
        [Parameter(Mandatory = $true)]
        $Node,

        [Parameter(Mandatory = $true)]
        [string]$BaseUrl
    )

    if ($null -eq $Node) {
        return $null
    }

    if ($Node -is [string]) {
        if ($Node.StartsWith("./")) {
            $relativePath = $Node.Substring(2).Replace("\", "/")
            return "$BaseUrl/$relativePath"
        }
        return $Node
    }

    if ($Node -is [System.Collections.IList]) {
        $result = New-Object System.Collections.ArrayList
        foreach ($item in $Node) {
            [void]$result.Add((Convert-RelativePathsToOnline -Node $item -BaseUrl $BaseUrl))
        }
        return $result
    }

    if ($Node -is [pscustomobject] -or $Node -is [hashtable]) {
        $result = [ordered]@{}
        foreach ($prop in $Node.PSObject.Properties) {
            $result[$prop.Name] = Convert-RelativePathsToOnline -Node $prop.Value -BaseUrl $BaseUrl
        }
        return [pscustomobject]$result
    }

    return $Node
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($InputJson)) {
    $InputJson = Join-Path $scriptDir "6455.json"
}
if ([string]::IsNullOrWhiteSpace($OutputJson)) {
    $OutputJson = Join-Path $scriptDir "6455.online.json"
}

$normalizedBaseUrl = $RawBaseUrl.Trim().TrimEnd("/")

if (-not ($normalizedBaseUrl -match '^https?://')) {
    throw "RawBaseUrl must be an http/https URL."
}

$jsonText = Get-Content -LiteralPath $InputJson -Raw -Encoding UTF8
$jsonObject = $jsonText | ConvertFrom-Json
$onlineObject = Convert-RelativePathsToOnline -Node $jsonObject -BaseUrl $normalizedBaseUrl
$onlineJson = $onlineObject | ConvertTo-Json -Depth 100

Set-Content -LiteralPath $OutputJson -Value $onlineJson -Encoding UTF8

Write-Output "Online config generated:"
Write-Output $OutputJson
