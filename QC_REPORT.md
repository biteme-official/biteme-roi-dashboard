# 🛠️ biteme-roi-dashboard 주간 종합 QC 리포트

생성일: 2026-07-01 | 분석 기준: main 브랜치 최신 커밋

---

## 🚨 1. High (최우선 수정 과제)

### ① 관리자 비밀번호 프론트엔드 소스코드 평문 노출

* **상세 진단:** 관리자 모드(사업부별 공헌이익 브레이크다운·일자별 드릴다운) 진입 비밀번호가 index.html 클라이언트 JavaScript 2327번째 줄에 평문 하드코딩. F12 → Sources 탭 한 번이면 누구나 확인 가능, URL을 아는 모든 접속자가 민감 재무 정보에 접근 가능.
* **[AS-IS]** `index.html:2327` → `if(pw==='****'){`
* **[TO-BE]** `api/admin-auth.js` 서버 엔드포인트 신규 생성, `process.env.ADMIN_PASSWORD` 환경변수와 비교. 클라이언트는 서버 OK/FAIL 응답만 수신.

### ② Avg. DAU 집계 기준 불일치 → CVR 단위 간 수십 배 왜곡

* **상세 진단:** Avg. DAU가 Y/Q 단위에서는 일별 평균, M/W 단위에서는 일별 합산으로 집계됨. 플랫폼 2025 연간 CVR = 32,590명 ÷ 12,508(일평균 DAU) × 100 = 약 260%, 같은 달 월간 CVR 계산 시 분모가 31일 합산(약 387,748)이 돼 약 0.7%. 연간-월간 KPI를 나란히 비교 시 CVR이 수백 배 차이 나 잘못된 의사결정 유발.
* **[AS-IS]** `api/tableau-data.js:208~226` — M·W 버킷은 AVG_MEASURES 평균 처리 없이 합산만. `index.html:909~915` — 프론트도 D레벨에서 `s+=dv` 합산 재집계.
* **[TO-BE]** M·W 루프에도 `measures[m] / cnt[gran][pk][m]` 평균 처리 추가. 프론트 렌더링도 `cnt++`로 카운트 후 `s/cnt` 평균으로 교체. platform 재집계 블록(347~364줄)도 동일 전환.

---

## ⚠️ 2. Medium (주요 개선 과제)

### ③ Footer 날짜 하드코딩
* **[AS-IS]** `index.html:510` — 데이터 ~2026-06-07 고정. 오늘 기준 24일 지난 날짜 표시.
* **[TO-BE]** `<span id="footerCutoff">` 동적 업데이트로 교체.

### ④ Tableau API 전체 실패
* **[AS-IS]** `api/tableau-data.js:302` — `Promise.all` 사용 시 단일 뷰 실패 시 전체 데이터 반환 실패.
* **[TO-BE]** `Promise.allSettled`로 변경해 단일 뷰 실패 시 나머지 데이터 정상 반환.

### ⑤ CORS 와일드카드
* **[AS-IS]** `api/tableau-data.js:294` — `'*'` 와일드카드 사용.
* **[TO-BE]** `process.env.ALLOWED_ORIGIN` 특정 도메인으로 제한.

### ⑥ 전역 event 객체
* **[AS-IS]** `index.html:2391` — `event.target` deprecated, Safari/strict mode 오류 가능.
* **[TO-BE]** `setQuickRange(preset, btn)`으로 `this` 전달 방식으로 교체.

---

## 💡 3. Low (향후 고도화 과제)

### ⑦ isoWeekKey 중복 구현
* `api/utils.js` 단일 소스로 추출 (서버/클라이언트 중복 제거)

### ⑧ LIVE 도트 freshness 미반영
* cutoff 경과 2일 이상 시 amber 도트로 교체

### ⑨ B2B 등급별 공헌이익 변동비 균등 배분 가정
* 코드 주석으로 명시

---

## 📋 수정 세션 시작 블록

아래 내용을 그대로 복사해서 Claude에게 붙여넣으면 바로 수정 작업을 시작합니다.

```
https://github.com/biteme-official/biteme-roi-dashboard 이번 주 QC 리포트 High 이슈 수정하자.
main 기준으로 20260701-bmdonghoon 브랜치 새로 만들고, 아래 항목 순서대로 수정해줘:

1. index.html 2325~2338번째 줄의 submitAdminPw() 함수에서 하드코딩된 비밀번호 비교를 제거하고, api/admin-auth.js 서버사이드 엔드포인트를 신규 생성해 process.env.ADMIN_PASSWORD와 비교하도록 전환하세요.
2. api/tableau-data.js 208~226번째 줄의 집계 루프에서 [M, W] 버킷에도 AVG_MEASURES 평균 나누기 처리를 추가하고, index.html 909~915번째 줄의 M/W DAU 렌더링 구간을 합산(s+=dv)에서 평균(s+=dv; cnt++; val=s/cnt)으로 수정하세요.
```
