param(
    [string]$BaseRef = "codex/research-assistant-core",
    [string]$WorktreeRoot = "",
    [switch]$WhatIfOnly
)

$ErrorActionPreference = "Stop"

function Invoke-Git {
    param([string[]]$Args)
    & git @Args
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Args -join ' ') failed with exit code $LASTEXITCODE"
    }
}

$repoRoot = (git rev-parse --show-toplevel).Trim()
if (-not $repoRoot) {
    throw "This script must be run inside a git repository."
}

if (-not $WorktreeRoot) {
    $parent = Split-Path -Parent $repoRoot
    $WorktreeRoot = Join-Path $parent "origin-ai-worktrees"
}

$branches = @(
    @{ Branch = "codex/unified-research-intake"; Path = "intake" },
    @{ Branch = "codex/comsol-result-export"; Path = "comsol-export" },
    @{ Branch = "codex/thermal-vv-harness"; Path = "vv-harness" },
    @{ Branch = "codex/thermal-visual-package"; Path = "visual-package" },
    @{ Branch = "codex/simulation-report-builder"; Path = "report-builder" },
    @{ Branch = "codex/research-assistant-workbench"; Path = "workbench" }
)

$dirty = git status --porcelain
if ($dirty) {
    Write-Warning "Current workspace has uncommitted changes. Worktrees are created from $BaseRef and will not include uncommitted changes."
    Write-Warning "Recommended: commit/stabilize codex/research-assistant-core first."
}

Write-Host "Repository: $repoRoot"
Write-Host "Base ref:    $BaseRef"
Write-Host "Worktrees:   $WorktreeRoot"

if (-not (Test-Path $WorktreeRoot) -and -not $WhatIfOnly) {
    New-Item -ItemType Directory -Path $WorktreeRoot | Out-Null
}

foreach ($item in $branches) {
    $branch = $item.Branch
    $path = Join-Path $WorktreeRoot $item.Path
    $branchExists = $false
    git show-ref --verify --quiet "refs/heads/$branch"
    if ($LASTEXITCODE -eq 0) {
        $branchExists = $true
    }

    if (Test-Path $path) {
        Write-Host "SKIP existing path: $path"
        continue
    }

    if ($WhatIfOnly) {
        if ($branchExists) {
            Write-Host "WHATIF git worktree add `"$path`" $branch"
        } else {
            Write-Host "WHATIF git worktree add -b $branch `"$path`" $BaseRef"
        }
        continue
    }

    if ($branchExists) {
        Invoke-Git @("worktree", "add", $path, $branch)
    } else {
        Invoke-Git @("worktree", "add", "-b", $branch, $path, $BaseRef)
    }
}

Write-Host ""
Write-Host "Done. Open each folder in a separate Codex conversation:"
foreach ($item in $branches) {
    Write-Host "- $(Join-Path $WorktreeRoot $item.Path)  [$($item.Branch)]"
}

