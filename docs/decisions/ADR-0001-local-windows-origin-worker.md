# ADR-0001: Origin 自动化使用本地 Windows Worker

## Status

Accepted

## Context

OriginLab 官方外部 Python 路线依赖 `originpro`，该包通过 Origin Automation Server COM 与本机 Origin 通信，且要求 Windows 和本机 Origin 2021+ 安装。科研用户也经常需要保留 Origin 项目文件、模板和本机许可。

## Decision

MVP 使用本地 Windows worker 运行 Origin 自动化。核心分析和验证逻辑保持为普通 Python 模块，不依赖 Origin。Origin 只负责最终项目和图表产物生成。

## Consequences

- 优点：符合官方接口，降低 GUI 自动化脆弱性，可直接复用 Origin 模板。
- 缺点：不能天然云端无头运行，部署依赖 Windows 和许可证。
- 缓解：无 Origin 时仍输出 JSON/plot spec；Origin worker 做成可选能力；未来可支持远程 Windows worker。
