#!/usr/bin/env python3
"""Ask Codex what to do next, then optionally post the answer to Slack."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "project.example.json"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_skill(config: dict[str, Any]) -> str:
    skill_path = config.get("skill_path")
    if not skill_path:
        return ""
    path = Path(skill_path).expanduser()
    if not path.exists():
        raise RuntimeError(f"skill_path does not exist: {path}")
    return path.read_text(encoding="utf-8")


def build_prompt(config: dict[str, Any]) -> str:
    project_name = config.get("project_name", "local project")
    skill = load_skill(config)
    if skill:
        return f"""
以下の SKILL.md の指示に厳密に従ってください。

<SKILL.md>
{skill}
</SKILL.md>

対象プロジェクト: {project_name}

このプロジェクトのメインセッションと現在の作業ディレクトリを必要な範囲で参照し、Slack 投稿本文だけを返してください。
""".strip()

    return f"""
このローカル環境の過去の Codex セッションや現在の作業ディレクトリを、必要な範囲だけ参照してください。
そのうえで、作業を前に進めるために人間へ送る Slack メッセージを書いてください。

対象プロジェクト: {project_name}

条件:
- 出力は Slack 投稿本文だけ
- 最大 4 行
- 1行目は必ず「お願い: ...してください。」で始める
- 依頼は、人間の判断・承認・確認が必要なものを具体的に 1 つだけ選ぶ
- 2行目で、その依頼がボトルネックになっている理由を短く書く
- 3行目で「その後Codexがやること: ...」を書く
- Codex だけで進められるなら、1行目は「お願い: ありません。Codex側で進めます。」にする
- 秘密情報や token は出さない
- 状況説明の羅列にしない。必ず次の行動を促す

推奨形式:
【{project_name}】
お願い: ...してください。
理由: ...
その後Codexがやること: ...
""".strip()


def ask_codex(config: dict[str, Any], prompt: str) -> str:
    project_path = Path(config.get("project_path", ROOT)).expanduser().resolve()
    codex_path = str(config.get("codex_path", "codex"))
    session_id = str(config.get("main_session_id", "")).strip()

    with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as out:
        output_path = Path(out.name)

    try:
        args = [
            codex_path,
            "--ask-for-approval",
            "never",
            "--cd",
            str(project_path),
            "--sandbox",
            "read-only",
            "exec",
        ]
        if session_id:
            args.extend(
                [
                    "resume",
                    "--skip-git-repo-check",
                    "--output-last-message",
                    str(output_path),
                    session_id,
                    prompt,
                ]
            )
        else:
            args.extend(
                [
                    "--skip-git-repo-check",
                    "--output-last-message",
                    str(output_path),
                    prompt,
                ]
            )
        proc = subprocess.run(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=int(config.get("codex_timeout_sec", 180)),
            check=False,
        )
        answer = output_path.read_text(encoding="utf-8", errors="replace").strip()
        if proc.returncode != 0:
            raise RuntimeError(proc.stdout.strip() or f"codex exited with {proc.returncode}")
        return answer or proc.stdout.strip()
    finally:
        try:
            output_path.unlink()
        except OSError:
            pass


def post_to_slack(config: dict[str, Any], text: str) -> None:
    token_env = str(config.get("slack_token_env", "SLACK_BOT_TOKEN"))
    token = os.environ.get(token_env)
    channel = config.get("slack_channel_id") or os.environ.get("SLACK_CHANNEL_ID")
    if not token:
        raise RuntimeError(f"{token_env} is not set")
    if not channel:
        raise RuntimeError("slack_channel_id or SLACK_CHANNEL_ID is not set")

    payload = {"channel": channel, "text": text, "unfurl_links": False, "unfurl_media": False}
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=int(config.get("slack_timeout_sec", 20))) as resp:
            result = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Slack HTTP {exc.code}: {body}") from exc

    if not result.get("ok"):
        raise RuntimeError(f"Slack API error: {result}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_json(Path(args.config).expanduser().resolve())
    load_env_file(Path(config.get("env_file", ROOT / ".local_agent" / "env")).expanduser())

    message = ask_codex(config, build_prompt(config))

    if args.dry_run:
        print(message)
    else:
        post_to_slack(config, message)
        print("posted to Slack")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
