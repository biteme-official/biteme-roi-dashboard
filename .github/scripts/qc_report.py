import anthropic
import os
import json
import re
import urllib.request
from datetime import datetime, timezone


def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"[읽기 실패: {e}]"


def count_issues(section_text):
    return len(re.findall(r"\* \*\*이슈 명칭:", section_text))


def extract_between(text, start_marker, end_markers):
    try:
        start = text.index(start_marker)
        end = len(text)
        for marker in end_markers:
            try:
                pos = text.index(marker, start + len(start_marker))
                if pos < end:
                    end = pos
            except ValueError:
                pass
        return text[start:end]
    except ValueError:
        return ""


# 소스 코드 읽기
index_html = read_file("index.html")
tableau_js = read_file("api/tableau-data.js")
server_js = read_file("server.js")

# 날짜/제목
now = datetime.now(timezone.utc)
today = now.strftime("%Y%m%d")
month = str(int(now.strftime("%m")))
week = now.strftime("%V")
year_short = now.strftime("%y")
wk_title = f"{year_short}년 {month}월 W{week} DailyROI QC 리포트"

# 프롬프트 조합 (f-string 사용 시 JS 템플릿 리터럴 충돌 방지를 위해 문자열 연결)
intro = (
    "너는 데이터 엔지니어링, 비즈니스 분석(BA), UI/UX 디자인을 모두 총괄하며, "
    "실제 프로덕트의 배포 우선순위를 결정하는 '치프 프로덕트 오피서(CPO)'이자 품질 관리(QC) 최고 책임자야.\n\n"
    "아래는 바잇미 사내 재무 ROI 대시보드의 현재 main 브랜치 소스 코드 전체야. "
    "코드를 직접 분석해서 실무진 관점에서 발견되는 모든 결함과 리스크를 진단해줘.\n\n"
    "이번 QC 리포트는 영역별 구분이나 점수 산정 없이, 오직 수정 우선순위(High / Medium / Low)로만 분류해줘. "
    "말로만 지적하는 것이 아니라 [AS-IS]와 [TO-BE] 형식으로 구체적으로 어떻게 고쳐야 하는지 작성해줘.\n\n"
    "---\n\n"
)

code_section = (
    "## index.html\n```html\n"
    + index_html
    + "\n```\n\n"
    "## api/tableau-data.js\n```javascript\n"
    + tableau_js
    + "\n```\n\n"
    "## server.js\n```javascript\n"
    + server_js
    + "\n```\n\n"
    "---\n\n"
)

instructions = (
    "보고서는 아래 마크다운 구조로 작성해줘.\n\n"
    "## 🛠️ biteme-roi-dashboard 주간 종합 QC 리포트\n\n"
    "### 🚨 1. High (최우선 수정 과제)\n"
    "*실무진의 의사결정에 치명적인 오류를 주거나, UI가 심각하게 깨지거나, 재무 데이터 왜곡(누락/계산 오류) 가능성이 있는 리스크*\n\n"
    "* **이슈 명칭:**\n"
    "  * **상세 진단:** 현재 코드나 로직에서 발견된 문제점과 실무진이 겪을 피해 기술\n"
    "  * **[AS-IS]:** 현재 소스 코드의 로직 또는 UI 상태\n"
    "  * **[TO-BE]:** 수정되어야 하는 최선의 소스 코드(로직) 또는 UI 설계안\n\n"
    "### ⚠️ 2. Medium (주요 개선 과제)\n"
    "*치명적이진 않지만 가독성을 크게 떨어뜨리거나, 특정 필터/조건에서 인터랙션 오류가 나거나, 데이터 해석에 혼선을 주는 리스크*\n\n"
    "* **이슈 명칭:**\n"
    "  * **상세 진단:** 문제점 및 실무진 사용성 저해 요인 기술\n"
    "  * **[AS-IS]:** 현재 상태\n"
    "  * **[TO-BE]:** 개선안 및 추천 방식\n\n"
    "### 💡 3. Low (향후 고도화 과제)\n"
    "*단순 오탈자, 마이너한 여백 불균형, 더 나은 인사이트를 위해 장기적으로 추가하면 좋은 기능적 제안*\n\n"
    "* **이슈 명칭:**\n"
    "  * **상세 진단:** 개선이 필요한 이유 기술\n"
    "  * **[AS-IS]:** 현재 상태\n"
    "  * **[TO-BE]:** 개선안\n\n"
    "### 🏃 이번 주 즉각 조치 사항 (Immediate Action Item)\n"
    "위에서 진단한 모든 이슈를 등급(High/Medium/Low)별로 구분해서, 각 이슈마다 "
    "\"어느 파일의 몇 번째 줄 부근을 어떻게 건드려야 하는지\" 알 수 있는 Claude 전달용 프롬프트를 작성해줘.\n\n"
    "**🚨 High**\n"
    "1. (해당 등급 이슈에 대한 수정 프롬프트)\n\n"
    "**⚠️ Medium**\n"
    "1. (해당 등급 이슈에 대한 수정 프롬프트)\n\n"
    "**💡 Low**\n"
    "1. (해당 등급 이슈에 대한 수정 프롬프트)\n\n"
    "(해당 등급에 이슈가 없으면 그 등급의 소제목과 항목을 통째로 생략)\n\n"
    "### 📋 수정 세션 시작 블록\n"
    "*High 이슈가 있는 경우에만 생성하세요. 없으면 통째로 생략하세요.*\n\n"
    "아래 내용을 그대로 복사해서 Claude에게 붙여넣으면 바로 수정 작업을 시작합니다.\n\n"
    "```\n"
    "https://github.com/biteme-official/biteme-roi-dashboard 이번 주 QC 리포트 High 이슈 수정하자.\n"
    "main 기준으로 " + today + "-bmdonghoon 브랜치 새로 만들고, 아래 항목 순서대로 수정해줘:\n"
    "[위 즉각 조치 사항 High 항목들을 번호 붙여 그대로 나열]\n"
    "```\n"
)

prompt = intro + code_section + instructions

# Claude API 호출
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8096,
    messages=[{"role": "user", "content": prompt}],
)

report = message.content[0].text
print("Claude API 응답 완료")

# QC_REPORT.md 저장
with open("QC_REPORT.md", "w", encoding="utf-8") as f:
    f.write(report)
print("QC_REPORT.md 저장 완료")

# 이슈 개수 카운트
high_section = extract_between(report, "### 🚨 1. High", ["### ⚠️", "### 💡", "### 🏃"])
med_section = extract_between(report, "### ⚠️ 2. Medium", ["### 💡", "### 🏃"])
low_section = extract_between(report, "### 💡 3. Low", ["### 🏃"])
high_count = count_issues(high_section)
med_count = count_issues(med_section)
low_count = count_issues(low_section)

# High 즉각조치사항 추출 (Slack 메시지용)
high_actions = extract_between(report, "**🚨 High**", ["**⚠️ Medium**", "**💡 Low**", "### 📋"])

# Slack 메시지 조합
github_link = "https://github.com/biteme-official/biteme-roi-dashboard/blob/main/QC_REPORT.md"
slack_text = (
    f"*{wk_title}*\n"
    f"🚨 High {high_count}건 | ⚠️ Medium {med_count}건 | 💡 Low {low_count}건"
)
if high_actions and len(slack_text) + len(high_actions) < 3500:
    slack_text += f"\n\n*📋 즉각 조치 사항 (High)*\n{high_actions.strip()}"
slack_text += f"\n\n🔗 전체 리포트: {github_link}"

# Slack 전송
webhook_url = os.environ["SLACK_WEBHOOK_URL"]
payload = json.dumps({"text": slack_text}).encode("utf-8")
req = urllib.request.Request(
    webhook_url,
    data=payload,
    headers={"Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(req) as resp:
        print(f"Slack 전송 성공: HTTP {resp.status}")
except Exception as e:
    print(f"Slack 전송 실패: {e}")
