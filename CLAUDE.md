# 작업 규칙

## 브랜치 · PR

- **main에 직접 push하지 않는다.** main에 머지되면 Vercel Production에 바로 배포된다.
- 작업은 항상 main 기준 새 브랜치에서 한다. 브랜치명: `<github아이디>/<YYYYMMDD>-<작업요약>` (예: `bmdonghoon/20260929-shopify-fix`)
- 작업이 끝나면 브랜치를 push하고 main 대상 PR을 만든다.
- PR 머지는 레포 관리자(@bmahsang, @bmhayoung)가 한다. 본인 PR을 직접 머지하지 않는다.
- force push, main 히스토리 재작성(rebase·reset 후 push)은 금지.
- 실수로 main에 push했다면 revert도 main에 직접 올리지 말고, 관리자에게 알린 뒤 PR로 처리한다.

> 현재 main 브랜치 보호(ruleset)가 설정돼 있지 않아 서버에서 강제되지 않는다. 이 규칙은 사람과 Claude가 지켜야 하는 약속이며, main에 들어오는 모든 push는 Slack 배포 알림(slack-deploy-notify)으로 기록된다.
