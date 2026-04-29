---
name: project-sweep-onboarding
description: "Codex Local Sweep を新しいプロジェクトへ導入するときに、config、project-sweep Skill、launchd plist、検証コマンドを安全に作成・確認するためのスキル。"
---

# Project Sweep Onboarding

Codex Local Sweep を新しいプロジェクトに導入する作業を支援する。
目的は、ユーザーが最小の判断だけで、プロジェクトごとの定期巡回を動かせる状態にすること。

## まず読むもの

runner root で次を確認する。

- `README.md`
- `add-project-sweep.md`
- `configs/project.example.json`
- `launchd/com.example.codex-sweep.project.plist.template`
- `skills/example_project_sweep/SKILL.md`

## 入力として集めるもの

分かるものは作業ディレクトリや既存ファイルから推定し、不明なものだけ短く聞く。

- `project_path`: 対象プロジェクトの絶対パス
- `project_slug`: launchd label 用の小文字ハイフン表記
- `project_name`: Slack 投稿に出す名前
- `slack_channel_id`: 投稿先チャンネル ID
- `main_session_id`: 継続利用する Codex セッション ID
- `schedule`: 日次・週次・時刻

secret や token は聞かない。Slack token は runner の `.local_agent/.env` にある前提で、config には env var 名だけを書く。

## 作成するもの

runner 側:

- `configs/<project_slug>.json`
- `skills/<project_slug>_project_sweep/SKILL.md`
- 必要なら `launchd/com.example.codex-sweep.<project_slug>.plist.template`

プロジェクト側:

- `<PROJECT_ROOT>/.codex/skills/project-sweep` を runner 側 skill への symlink にする

実運用 config、実 skill、実 plist は機密や個人パスを含みやすい。公開 repo では `.gitignore` の対象にする。

## 実装手順

1. `project_slug` を決める。launchd label は `com.example.codex-sweep.<project_slug>` を基本形にする。
2. `skills/example_project_sweep/SKILL.md` を `skills/<project_slug>_project_sweep/SKILL.md` にコピーする。
3. 対象プロジェクトを軽く読んで、project skill の「プロジェクト固有ルール」を具体化する。
4. `configs/project.example.json` を `configs/<project_slug>.json` にコピーし、絶対パス、Slack channel、session id、skill path を埋める。
5. `<PROJECT_ROOT>/.codex/skills/project-sweep` を runner 側 skill へ symlink する。既存 path がある場合は中身を確認してから扱う。
6. launchd plist はテンプレートから作る。`~/Library/LaunchAgents` へ直接書く場合は、ユーザーの意図と権限を確認する。
7. dry-run、Slack 投稿、launchd kickstart の順で確認する。

## 検証コマンド

config のパス確認:

```sh
python3 - <<'PY'
import json
from pathlib import Path
cfg=json.load(open('configs/<project_slug>.json'))
for key in ['project_path', 'codex_path', 'env_file', 'skill_path']:
    p=Path(cfg[key]).expanduser()
    print(f'{key}: {p} exists={p.exists()}')
PY
```

dry-run:

```sh
/usr/bin/python3 scripts/codex_local_sweep.py \
  --config configs/<project_slug>.json \
  --dry-run
```

launchd:

```sh
plutil -lint ~/Library/LaunchAgents/com.example.codex-sweep.<project_slug>.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.codex-sweep.<project_slug>.plist
launchctl enable gui/$(id -u)/com.example.codex-sweep.<project_slug>
launchctl kickstart -k gui/$(id -u)/com.example.codex-sweep.<project_slug>
launchctl print gui/$(id -u)/com.example.codex-sweep.<project_slug> | sed -n '1,70p'
```

成功条件:

- dry-run で Slack 投稿文だけが出る
- Slack 実送信で対象チャンネルに投稿される
- launchd の `last exit code = 0`
- `.local_agent/<project_slug>.err.log` に新しいエラーがない

## 失敗時の見方

- `Could not find service`: label 名か bootstrap が未完了。
- `Bootstrap failed: 5`: plist 構文、label 重複、パス間違いを確認。
- `env: node: No such file or directory`: plist の `PATH` に Node.js を含める。
- `Operation not permitted`: macOS 権限。runner 配下に skill を置き、プロジェクト側は symlink にする。
- Slack 投稿なし: `err.log`、`last exit code`、`slack_channel_id`、token env を確認。

## 最後にユーザーへ返すこと

- 作成・変更したファイル
- ユーザーが実行するコマンド
- 未設定の値があればその一覧
- dry-run または launchd 検証の結果
