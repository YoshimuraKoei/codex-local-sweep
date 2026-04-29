# Codex Local Sweep

Mac の `launchd` と `codex exec` を使って、ローカルの Codex エージェントを定期実行し、Slack に短い巡回メッセージを投稿するための小さな runner です。

## できること

- プロジェクトごとの config を読み込む
- `codex exec` または `codex exec resume <session_id>` を read-only で実行する
- プロジェクトごとの `SKILL.md` をプロンプトに含める
- Codex の最終応答を Slack `chat.postMessage` で投稿する
- `launchd` から日次・週次などで定期実行する

## 基本構成

```text
scripts/
  codex_local_sweep.py
configs/
  project.example.json
skills/
  example_project_sweep/
    SKILL.md
  project_sweep_onboarding/
    SKILL.md
launchd/
  com.example.codex-sweep.project.plist.template
.local_agent/
  .env
  *.log
```

`.local_agent/` と実運用 config は Git 管理しない想定です。

## セットアップ

Slack Bot token を `.local_agent/.env` に置きます。

```sh
mkdir -p .local_agent
printf 'SLACK_BOT_TOKEN=replace-with-your-token\n' > .local_agent/.env
```

プロジェクト用 config は example から作ります。

```sh
cp configs/project.example.json configs/my_project.json
```

`configs/my_project.json` の `project_path`, `slack_channel_id`, `skill_path`, `main_session_id` などを自分の環境に合わせます。

## 手動テスト

Slack に送らず文面だけ確認します。

```sh
/usr/bin/python3 scripts/codex_local_sweep.py \
  --config configs/my_project.json \
  --dry-run
```

Slack に投稿します。

```sh
/usr/bin/python3 scripts/codex_local_sweep.py \
  --config configs/my_project.json
```

## launchd

`launchd/com.example.codex-sweep.project.plist.template` をコピーし、パス、label、config、ログ出力先、実行時刻を編集します。

```sh
cp launchd/com.example.codex-sweep.project.plist.template \
  ~/Library/LaunchAgents/com.example.codex-sweep.my-project.plist
```

登録します。

```sh
launchctl bootstrap gui/$(id -u) \
  ~/Library/LaunchAgents/com.example.codex-sweep.my-project.plist

launchctl enable gui/$(id -u)/com.example.codex-sweep.my-project
```

手動起動します。

```sh
launchctl kickstart -k gui/$(id -u)/com.example.codex-sweep.my-project
```

状態確認:

```sh
launchctl print gui/$(id -u)/com.example.codex-sweep.my-project | sed -n '1,70p'
```

`last exit code = 0` なら直近実行は成功です。

## 複数プロジェクト

プロジェクトごとの config、skill、session id、LaunchAgent を追加する手順は [add-project-sweep.md](add-project-sweep.md) を参照してください。

Codex に導入作業を任せる場合は、`skills/project_sweep_onboarding/` を使うと、config、project skill、plist、検証コマンドの準備をまとめて進められます。
