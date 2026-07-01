"""
QC_REPORT.md를 읽어 Slack Block Kit 형식으로 변환 후 인커밍 웹훅으로 전송.

사용법:
    $env:SLACK_WEBHOOK_URL = "https://hooks.slack.com/..."
    python scripts/send_qc_report.py

환경변수:
    SLACK_WEBHOOK_URL  Slack 인커밍 웹훅 URL (필수)
    REPORT_PATH        QC_REPORT.md 경로 (기본값: ./QC_REPORT.md)
"""

import json
import os
import re
import urllib.request
from pathlib import Path


def md_to_mrkdwn(text: str) -> str:
    """Markdown 일부를 Slack mrkdwn으로 변환."""
    # **bold** → *bold*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    # ### 소제목 → *소제목*
    text = re.sub(r"^#{1,3}\s+", "", text, flags=re.MULTILINE)
    # --- 구분선 제거
    text = re.sub(r"^-{3,}$", "", text, flags=re.MULTILINE)
    # 코드블록 마커(```) 제거
    text = re.sub(r"^```.*$", "", text, flags=re.MULTILINE)
    # 연속 빈줄 정리
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_sections(report_text: str) -> list[dict]:
    """QC_REPORT.md를 섹션 단위로 파싱해 Block Kit 블록 리스트 반환."""
    blocks = []

    # 헤더 블록
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": ":hammer_and_wrench: biteme-roi-dashboard QC 리포트", "emoji": True},
    })

    # 생성일 파싱
    date_match = re.search(r"생성일:\s*(.+?)\s*\|", report_text)
    if date_match:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f":calendar: *생성일:* {date_match.group(1)}  |  분석 기준: main 브랜치 최신 커밋"},
        })

    blocks.append({"type": "divider"})

    # ## 단위로 섹션 분리
    sections = re.split(r"\n## ", report_text)
    for section in sections[1:]:  # 첫 번째는 헤더 위 내용
        lines = section.strip().splitlines()
        title_raw = lines[0].strip()
        body = "\n".join(lines[1:]).strip()

        # 섹션 제목 이모지 매핑
        if "High" in title_raw:
            emoji = ":rotating_light:"
        elif "Medium" in title_raw:
            emoji = ":warning:"
        elif "Low" in title_raw:
            emoji = ":bulb:"
        elif "수정 세션" in title_raw:
            emoji = ":clipboard:"
        else:
            emoji = ":white_small_square:"

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"{emoji} *{title_raw}*"},
        })

        # 수정 세션 블록은 ### 없이 코드블록 본문 직접 추출
        if "수정 세션" in title_raw:
            code_match = re.search(r"```(.*?)```", body, re.DOTALL)
            if code_match:
                code_content = code_match.group(1).strip()
                if len(code_content) > 2900:
                    code_content = code_content[:2900] + "\n…(생략)"
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f":point_right: 아래 내용을 Claude Code에 붙여넣으면 바로 수정 작업을 시작합니다.\n\n```{code_content}```"},
                })
            blocks.append({"type": "divider"})
            continue

        # ### 단위로 항목 분리
        items = re.split(r"\n### ", body)
        for item in items:
            if not item.strip():
                continue
            item_lines = item.strip().splitlines()
            item_title = item_lines[0].strip()
            item_body = "\n".join(item_lines[1:]).strip()

            converted = md_to_mrkdwn(item_body)
            if len(converted) > 2900:
                converted = converted[:2900] + "\n…(생략)"

            text = f"*{item_title}*\n{converted}" if converted else f"*{item_title}*"
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": text},
            })

        blocks.append({"type": "divider"})

    return blocks


def send(webhook_url: str, blocks: list[dict]) -> None:
    payload = {"blocks": blocks}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode()
        if body != "ok":
            raise RuntimeError(f"Slack 오류: {body}")


def main() -> None:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise SystemExit("SLACK_WEBHOOK_URL 환경변수를 설정해주세요.")

    report_path = os.environ.get("REPORT_PATH", "QC_REPORT.md")
    if not Path(report_path).exists():
        raise SystemExit(f"파일을 찾을 수 없어요: {report_path}")

    report = Path(report_path).read_text(encoding="utf-8")
    blocks = parse_sections(report)
    send(webhook_url, blocks)
    print("Slack 전송 완료")


if __name__ == "__main__":
    main()
