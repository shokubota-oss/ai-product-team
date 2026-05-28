# AI Product Team

AIエージェントが役割を持ってGitHub Issues経由で協調する製品開発チームハーネス。

## エージェント一覧

| エージェント | フォルダ | Cron | 役割 |
|---|---|---|---|
| Orchestrator | ルート `CLAUDE.md` | 毎時15分 | Issue振り分け・進捗監視 |
| PdM | `agents/pdm/` | 平日9:00 | 要件定義・PRD作成 |
| UX | `agents/ux/` | 平日9:30 | UX仕様・ユーザーフロー |
| Finance | `agents/finance/` | 平日10:00 | ROI・財務分析 |
| Engineer | `agents/engineer/` | 平日10:30 | 実装・PR作成 |
| **Designer** | `agents/designer/` | 平日11:30 | デザイン仕様・画像管理 |

## GitHub Labels

- **ロール**: `agent:orchestrator` `agent:pdm` `agent:ux` `agent:finance` `agent:engineer` `agent:designer`
- **ステータス**: `status:new` `status:in-progress` `status:handoff` `status:blocked` `status:done`
- **優先度**: `priority:critical` `priority:high` `priority:medium` `priority:low`
- **タイプ**: `type:feature` `type:research` `type:bug` `type:epic`

## ワークフロー

```
Issue作成（status:new）
  → Orchestrator がエージェントラベルを付与
  → 各エージェントが担当Issueを処理・成果物をコミット
  → Handoff Issueで次のエージェントに引き継ぎ
  → 全完了でIssueクローズ
```

## ディレクトリ構造

```
ai-product-team/
├── CLAUDE.md               # Orchestratorペルソナ
├── agents/
│   ├── pdm/CLAUDE.md
│   ├── ux/CLAUDE.md
│   ├── finance/CLAUDE.md
│   ├── engineer/CLAUDE.md
│   └── designer/
│       ├── CLAUDE.md
│       └── memory/         # デザイナー知識ベース
├── specs/                  # PdMが作成する仕様書
├── designs/                # UX・Designerが作成するデザイン仕様
├── finance/                # 財務分析レポート
└── src/                    # エンジニアが実装するコード
```
