# 王二小修改版 — 一键更新脚本
# 使用 gh CLI 认证，无需手动填写 Token
# 使用方式：双击 一键上传更新.bat 即可

$Owner = "github86525"
$Repo = "wang-er-xiao-tvbox"
$BaseUrl = "https://raw.githubusercontent.com/$Owner/$Repo/main"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Output "=================================="
Write-Output " 王二小修改版 — 一键更新上传"
Write-Output "=================================="
Write-Output ""

# 第1步：重新生成 6455.online.json
Write-Output "[1/3] 重新生成在线配置文件..."
$buildScript = Join-Path $ScriptDir "build-online-config.ps1"
& powershell -ExecutionPolicy Bypass -File $buildScript -RawBaseUrl $BaseUrl

# 第2步：生成 API Token (用 gh CLI)
Write-Output "[2/3] 获取 GitHub 认证..."
$tokenJson = gh auth token 2>$null
if (-not $tokenJson) {
    Write-Output "  ✗ 未登录 GitHub，请先运行: gh auth login --web"
    exit 1
}
$Token = $tokenJson.Trim()
$headers = @{
    "Authorization" = "token $Token"
    "Accept" = "application/vnd.github.v3+json"
}
$apiBase = "https://api.github.com/repos/$Owner/$Repo"

Write-Output "  ✓ 认证成功 ($Owner/$Repo)"

# 获取当前最新 commit SHA
$ref = Invoke-RestMethod -Uri "$apiBase/git/refs/heads/main" -Headers $headers
$latestCommit = Invoke-RestMethod -Uri "$apiBase/git/commits/$($ref.object.sha)" -Headers $headers
$baseTreeSha = $latestCommit.tree.sha

# 要上传的文件列表
$filesToUpload = @(
    @{ path = "6455.json"; desc = "本地配置" },
    @{ path = "6455.online.json"; desc = "在线配置" }
)

# 额外文件
$extraFiles = Get-ChildItem -Path $ScriptDir -Recurse -File | Where-Object {
    $_.FullName -notmatch '\.git\\' -and
    $_.Name -notlike '6455.*' -and
    $_.Name -ne 'README.md' -and
    $_.Name -ne 'build-online-config.ps1' -and
    $_.Name -ne 'update-to-github.ps1' -and
    $_.Name -notlike '*.bat'
}
foreach ($f in $extraFiles) {
    $relPath = $f.FullName.Substring($ScriptDir.Length + 1) -replace '\\', '/'
    $filesToUpload += @{ path = $relPath; desc = $relPath }
}

# 创建 blob 并上传
$newBlobs = [System.Collections.ArrayList]@()
foreach ($file in $filesToUpload) {
    $fullPath = Join-Path $ScriptDir $file.path
    if (-not (Test-Path $fullPath)) {
        Write-Output "  ⚠ 跳过: $($file.path) (不存在)"
        continue
    }
    $bytes = [System.IO.File]::ReadAllBytes($fullPath)
    $base64Content = [System.Convert]::ToBase64String($bytes)
    $blobBody = @{ content = $base64Content; encoding = "base64" } | ConvertTo-Json -Depth 10
    try {
        $blob = Invoke-RestMethod -Uri "$apiBase/git/blobs" -Method Post -Headers $headers -Body $blobBody -ContentType "application/json"
        [void]$newBlobs.Add(@{ path = $file.path; mode = "100644"; type = "blob"; sha = $blob.sha })
        Write-Output "  ✓ $($file.desc)"
    } catch {
        Write-Output "  ✗ $($file.desc) — 失败: $_"
    }
}

# 创建新的 tree
Write-Output "[3/3] 提交更新..."
$treeBody = @{
    base_tree = $baseTreeSha
    tree = $newBlobs
} | ConvertTo-Json -Depth 10
$tree = Invoke-RestMethod -Uri "$apiBase/git/trees" -Method Post -Headers $headers -Body $treeBody -ContentType "application/json"

$commitBody = @{
    message = "一键更新: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    tree = $tree.sha
    parents = @($ref.object.sha)
} | ConvertTo-Json -Depth 10
$commit = Invoke-RestMethod -Uri "$apiBase/git/commits" -Method Post -Headers $headers -Body $commitBody -ContentType "application/json"

$refBody = @{ sha = $commit.sha; force = $true } | ConvertTo-Json
Invoke-RestMethod -Uri "$apiBase/git/refs/heads/main" -Method Patch -Headers $headers -Body $refBody -ContentType "application/json"

Write-Output "  ✓ 提交成功: $($commit.sha.Substring(0,7))"
Write-Output ""
Write-Output "=================================="
Write-Output " ✅ 更新完成！"
Write-Output "=================================="
Write-Output "在线接口地址:"
Write-Output "https://raw.githubusercontent.com/$Owner/$Repo/main/6455.online.json"
Write-Output ""
Write-Output "jsDelivr CDN:"
Write-Output "https://cdn.jsdelivr.net/gh/$Owner/$Repo@main/6455.online.json"
Write-Output ""
Write-Output "📱 手机端（OK影视）推荐填入:"
Write-Output "https://cdn.jsdelivr.net/gh/$Owner/$Repo@main/6455.online.json"
