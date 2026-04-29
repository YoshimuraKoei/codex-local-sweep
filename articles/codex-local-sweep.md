---
title: "Codex の非対話モードでプロジェクトのタスク管理を楽にしようぜ"
emoji: "📝"
type: "idea" 
topics: ["codex", "launchd", "slack"]
published: false
---

# Codex Local Sweep

## 概要

Mac の `launchd` による定期実行と Codex の非対話モード `codex exec` により、プロジェクトでやるべきタスクを Slack で毎朝報告してくれるエージェントを構築する。

得たい成果は、**多数のプロジェクトにおいて、毎回人間が取り組むべきタスクを考えるコストを減らすこと**。そのためのソリューションとして、今回はローカルの Codex をメインセッション上で定期実行させ、そのプロジェクトでの次取り組むべきタスクを洗い出させる。その結果を Slack API でチャンネルに投稿する。

https://github.com/YoshimuraKoei/codex-local-sweep

![Slack に投稿される巡回メッセージの例](/images/slack.png)

### 課題

課題として、

1. **複数プロジェクトで何をしていたのか・何をすべきなのかがわからなくなってしまう**
→ AI を複数プロジェクトで運用するにあたり、人間の管理コストがネックになる
    - 期間が空いた時に、以前何をしていたのかがわからない。
    - AI エージェントが動くべきなのに止まってしまっている（= 指示待ち) のか、人間が行うべき作業を行っていないから AI エージェントが作業を進めれないのかが分からない。
2. **各プロジェクトで次何をすべきか調べるときに、各プロジェクトのディレクトリで作業の様子を把握するのが面倒**
    - 進捗を振り返ってタスクの順番を決めたいだけなのに、いちいち調べにいく必要がある
    → どこかで一元管理して把握したい

のようなものが挙げられる。このような管理コストに関しては、2種類のアプローチがある。

1. **push 型**
    - 自身で情報を把握しやすいように情報を整理する
2. **pull 型**
    - 自身が求める情報を自動化などの手段で整理したものを見る

この記事は 2 の pull 型でのソリューションの提案である。

### 動作イメージ

シンプルな構成になっている。

1. launchd で定期実行が走る
2. `codex exec` または `codex exec resume <session_id>` を実行する
3. プロジェクトごとの `SKILL.md` をプロンプトに含める
4. Codex の最終応答を Slack `chat.postMessage` で投稿する

![drawio による動作フローのイメージ図](/images/codex-local-sweep-flow.drawio.png)

## 基本構成

```text
.
├── scripts/
│   └── codex_local_sweep.py
├── configs/
│   └── project.example.json
├── skills/
│   ├── example_project_sweep/
│   │   └── SKILL.md
│   └── project_sweep_onboarding/
│       └── SKILL.md
├── launchd/
│   └── com.example.codex-sweep.project.plist.template
└── .local_agent/
    ├── .env
    └── *.log
```

## セットアップ

【前提条件】
- Codex CLI
- Python (version 3以上であれば多分大丈夫)

ここでは Slack Bot の導入手順は紹介しない。
下記の記事が参考になると思われる。

https://qiita.com/odm_knpr0122/items/04c342ec8d9fe85e0fe9

### 1. 作成した Slack Bot token を `.local_agent/.env` に置く。

```sh
mkdir -p .local_agent
printf 'SLACK_BOT_TOKEN=replace-with-your-token\n' > .local_agent/.env
```

### 2. プロジェクト用 config は example を参考に作る。

```sh
cp configs/project.example.json configs/my_project.json
```

```json
{
  "project_name": "project-slug",
  "project_path": "/ABSOLUTE/PATH/TO/YOUR/PROJECT",
  "codex_path": "/opt/homebrew/bin/codex",
  "codex_timeout_sec": 300,
  "slack_token_env": "SLACK_BOT_TOKEN",
  "slack_channel_id": "CXXXXXXXXXX",
  "env_file": "/ABSOLUTE/PATH/TO/codex_test/.local_agent/.env",
  "slack_timeout_sec": 20,
  "skill_path": "/ABSOLUTE/PATH/TO/codex_test/skills/example_project_sweep/SKILL.md",
  "main_session_id": "019xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

- `project_path`
    - このツールを導入したいプロジェクトのパス
- `slack_channel_id`
    - AI エージェントが報告する Slack のチャンネル ID
- `main_session_id`
    - Codex で利用したいセッションの ID 

### 3. プロジェクト用の Agent Skills を作る

この仕組みでは、プロジェクトごとに Agent Skills を利用する（必須ではないが）。
そうすることで、各プロジェクトごとに応じて AI エージェントの振る舞いを制御することができるからである。

`SKILL.md` には、定期実行される Codex に対する巡回ルールを定めておく。
具体的には、 Codex が Slack に投稿する内容を決めるための判断基準を書いておく。

1. まず何を読めば状況がわかるか
2. どんなときに人間へ依頼すべきか
3. 人間の確認が終わったら Codex が何を進めるべきか

例えば、次のように書く。

```md
---
name: project-sweep
description: "定期実行されるプロジェクト巡回で、人間がボトルネックになっている判断や確認を1つ特定し、Slack投稿文を作るためのスキル。"
---

# Project Sweep

あなたはこのプロジェクトを定期巡回するローカル Codex エージェント。

## まず読むもの

- `TASK.md`
- `README.md`
- `docs/roadmap.md`
- GitHub Issues

## 人間に依頼すべきこと

- 実験結果の採用・不採用の判断
- 方針変更の承認
- 外部サービスへのログインや認証
- Slack や GitHub 上での最終確認
- Codex が勝手に決めると危ない優先順位の判断

## Codex が自律的に進めてよいこと

- Issue の下書き
- 実験コマンドの整理
- ドキュメント更新案の作成
- 小さなコード修正案の作成
- 次に読むべきファイルの整理

## 出力形式

Slack 投稿本文だけを返してください。

【プロジェクト】
<project_name>

【お願い】
...してください。

【理由】
...

【その後Codexがやること】
...

## ルール
  - 人間に依頼する内容は1つだけにする
  - 状況説明だけで終わらせない
  - 「何をしてほしいか」を最初に書く
  - secret、token、個人情報は出さない
  - Codex だけで進められる場合も、次に投げるべき指示を明確にする

```

### 4. 手動テスト

Slack に送らず文面だけ確認する。

```sh
/usr/bin/python3 scripts/codex_local_sweep.py \
  --config configs/my_project.json \
  --dry-run
```

Slack に投稿する。

```sh
/usr/bin/python3 scripts/codex_local_sweep.py \
  --config configs/my_project.json
```

### 5. launchd の設定

`launchd/com.example.codex-sweep.project.plist.template` をコピーし、パス、label、config、ログ出力先、実行時刻を編集する。
macOS では、ユーザー単位の定期実行設定を `~/Library/LaunchAgents/` に置く。

```sh
cp launchd/com.example.codex-sweep.project.plist.template \
  ~/Library/LaunchAgents/com.example.codex-sweep.my-project.plist
```

編集する。

```sh
vim ~/Library/LaunchAgents/com.example.codex-sweep.my-project.plist
```

主に変更するのは次の項目。

- `Label`: `launchctl` で指定する service 名
- `ProgramArguments`: runner script と config の絶対パス
- `WorkingDirectory`: このリポジトリの絶対パス
- `StartCalendarInterval`: 実行タイミング
- `StandardOutPath` / `StandardErrorPath`: ログ出力先


launchctl で登録する。

```sh
launchctl bootstrap gui/$(id -u) \
  ~/Library/LaunchAgents/com.example.codex-sweep.my-project.plist

launchctl enable gui/$(id -u)/com.example.codex-sweep.my-project
```

手動起動させて動作確認をする。

```sh
launchctl kickstart -k gui/$(id -u)/com.example.codex-sweep.my-project
```

状態確認:

```sh
launchctl print gui/$(id -u)/com.example.codex-sweep.my-project | sed -n '1,70p'
```

`last exit code = 0` なら直近実行は成功。

plist を編集した場合は、保存するだけでは反映されないため、変更後は再登録する。

```sh
launchctl bootout gui/$(id -u)/com.example.codex-sweep.my-project

launchctl bootstrap gui/$(id -u) \
  ~/Library/LaunchAgents/com.example.codex-sweep.my-project.plist

launchctl enable gui/$(id -u)/com.example.codex-sweep.my-project
```

## 複数プロジェクト

プロジェクトごとの config、skill、session id、LaunchAgent を追加する手順は [add-project-sweep.md](add-project-sweep.md) を参照する。Codex に導入作業を任せる場合は、`skills/project_sweep_onboarding/` を使うと、config、project skill、plist、検証コマンドの準備をまとめて進められる。
