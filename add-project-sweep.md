# プロジェクト巡回を追加する手順

この手順書は、1つのプロジェクトに対して Codex の定期巡回を追加するためのものです。

Codex に導入作業を任せる場合は、`skills/project_sweep_onboarding/` の Skill を使います。
人間が自分で作業する場合は、この手順を上から実行します。

基本方針は次です。

```text
1プロジェクト = 1 config = 1 LaunchAgent = 1 Slack 投稿先
```

以下では runner の配置先を `<RUNNER_ROOT>` と書きます。

```text
<RUNNER_ROOT>/scripts/codex_local_sweep.py
```

## 1. プロジェクト slug を決める

launchd の label には、小文字とハイフンの slug を使います。

例:

```text
my-project
```

JSON ファイル名はアンダースコアでも構いません。

```text
configs/my_project.json
```

注意点:

- launchd の `Label` と `launchctl kickstart` で指定する名前は完全一致させる。
- `my-project` と `my_project` のズレで `kickstart` や `bootstrap` が失敗する。

## 2. プロジェクト用 Skill を作る

対象プロジェクト側に skill を作ります。

```text
<PROJECT_ROOT>/.codex/skills/project-sweep/SKILL.md
```

例:

```md
---
name: project-sweep
description: "定期実行されるプロジェクト巡回で、人間がボトルネックになっている判断を1つ特定し、Slack投稿文を作るためのスキル。"
---
```

launchd から起動された Python は、macOS の権限設定により `~/Documents` 配下のファイルを読めないことがあります。
その場合は、project repo 側の skill を runner 側にミラーします。

```sh
mkdir -p <RUNNER_ROOT>/skills/<project_slug>_project_sweep
cp <PROJECT_ROOT>/.codex/skills/project-sweep/SKILL.md \
  <RUNNER_ROOT>/skills/<project_slug>_project_sweep/SKILL.md
```

シンボリックリンクを貼る例:

```sh
ln -s <RUNNER_ROOT>/skills/<project_slug>_project_sweep \
  <PROJECT_ROOT>/.codex/skills/project-sweep
```

runner の config では、runner 側の `SKILL.md` を `skill_path` に指定します。

## 3. メインセッション ID を決める

プロジェクトの文脈を持っている Codex セッション ID を控えます。

config には次のように書きます。

```json
"main_session_id": "019..."
```

セッション ID により、毎回新規セッションではなく、プロジェクトの継続文脈を使った巡回になります。

## 4. プロジェクト config を作る

runner 側に config を作ります。

```text
<RUNNER_ROOT>/configs/<project>.json
```

例:

```json
{
  "project_name": "my_project",
  "project_path": "/absolute/path/to/project/workdir",
  "codex_path": "/opt/homebrew/bin/codex",
  "codex_timeout_sec": 300,
  "slack_token_env": "SLACK_BOT_TOKEN",
  "slack_channel_id": "<CHANNEL_ID>",
  "env_file": "<RUNNER_ROOT>/.local_agent/.env",
  "slack_timeout_sec": 20,
  "skill_path": "<RUNNER_ROOT>/skills/<project_slug>_project_sweep/SKILL.md",
  "main_session_id": "019..."
}
```

各項目の意味:

- `project_name`: Slack 投稿に出すプロジェクト名。
- `project_path`: Codex を実行する作業ディレクトリ。
- `codex_path`: Codex CLI のパス。
- `slack_channel_id`: 投稿先 Slack チャンネル。
- `env_file`: Slack token を読む env ファイル。
- `skill_path`: runner 側の `SKILL.md`。
- `main_session_id`: resume する Codex セッション ID。

パスが存在するか確認します。

```sh
python3 - <<'PY'
import json
from pathlib import Path
cfg=json.load(open('<RUNNER_ROOT>/configs/<project>.json'))
for key in ['project_path', 'codex_path', 'env_file', 'skill_path']:
    p=Path(cfg[key]).expanduser()
    print(f'{key}: {p} exists={p.exists()}')
PY
```

すべて `exists=True` になれば OK です。

## 5. launchd の前に dry-run する

まず Slack に投稿せず、文面だけ確認します。

```sh
/usr/bin/python3 <RUNNER_ROOT>/scripts/codex_local_sweep.py \
  --config <RUNNER_ROOT>/configs/<project>.json \
  --dry-run
```

ここで失敗する場合は、launchd に進まず、config、skill、セッション ID を先に直します。

## 6. LaunchAgent plist を作る

プロジェクトごとに plist を作ります。

```text
~/Library/LaunchAgents/com.example.codex-sweep.<project_slug>.plist
```

`launchd/com.example.codex-sweep.project.plist.template` をコピーし、以下を置き換えます。

- `com.example.codex-sweep.project-slug`
- `/ABSOLUTE/PATH/TO/codex_test`
- `project.example.json`
- `project-slug`
- 実行時刻

重要な確認点:

- `Label` は `launchctl` で指定する service 名と完全一致させる。
- `ProgramArguments` の config path が正しいこと。
- `StandardOutPath` と `StandardErrorPath` はプロジェクトごとに分ける。
- `PATH` に Node.js の場所を含める。`codex` は `#!/usr/bin/env node` なので、launchd 環境で Node.js が見えないと落ちる。

plist を検証します。

```sh
plutil -lint ~/Library/LaunchAgents/com.example.codex-sweep.<project_slug>.plist
plutil -p ~/Library/LaunchAgents/com.example.codex-sweep.<project_slug>.plist
```

## 7. 登録してテストする

登録します。

```sh
launchctl bootstrap gui/$(id -u) \
  ~/Library/LaunchAgents/com.example.codex-sweep.<project_slug>.plist

launchctl enable gui/$(id -u)/com.example.codex-sweep.<project_slug>
```

手動実行します。

```sh
launchctl kickstart -k gui/$(id -u)/com.example.codex-sweep.<project_slug>
```

状態を確認します。

```sh
launchctl print gui/$(id -u)/com.example.codex-sweep.<project_slug> | sed -n '1,70p'
```

見るところ:

```text
runs = ...
last exit code = 0
```

ログを確認します。

```sh
tail -f <RUNNER_ROOT>/.local_agent/<project_slug>.out.log
tail -f <RUNNER_ROOT>/.local_agent/<project_slug>.err.log
```

成功時は `out.log` に次が出ます。

```text
posted to Slack
```

## 8. plist を変更したとき

plist を編集して保存するだけでは、launchd には反映されません。

変更後は読み直します。

```sh
launchctl bootout gui/$(id -u)/com.example.codex-sweep.<project_slug>
launchctl bootstrap gui/$(id -u) \
  ~/Library/LaunchAgents/com.example.codex-sweep.<project_slug>.plist
launchctl enable gui/$(id -u)/com.example.codex-sweep.<project_slug>
```

その後、`kickstart` で確認します。

## よくある失敗

### `Bootstrap failed: 5: Input/output error`

確認すること:

- `plutil -lint` が OK か。
- `Label` と service 名が一致しているか。
- config path が存在するか。
- 同じ label がすでに登録されていないか。登録済みなら `bootout` してから `bootstrap` する。

### `env: node: No such file or directory`

launchd の `PATH` に Node.js がありません。

plist の `EnvironmentVariables` で `PATH` を指定します。

### `PermissionError: Operation not permitted`

launchd から起動された Python が protected directory 配下を読めないことがあります。

対処:

- `SKILL.md` は runner 側の `<RUNNER_ROOT>/skills/...` にミラーする。
- config、env、ログは runner 配下に置く。
- `skill_path` はミラー先を指す。

### Slack に投稿されない

確認すること:

- `launchctl print ...` の `last exit code`。
- `<project_slug>.err.log`。
- `.local_agent/.env` に `SLACK_BOT_TOKEN` があるか。
- Slack bot が投稿先チャンネルに追加されているか。
