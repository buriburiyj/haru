# Haru — 최종 기획서 (SPEC.md)

## 0. 목표와 기한
- Claude 앱(Chat·Cowork·Code)과 똑같은 구조의 개인 비서 앱을 0원으로 만든다. 가능한 곳은 Claude보다 좋게.
- 이름: Haru. 말투: 존댓말 "~했습니다/~입니다".
- 맥: Swift로 감싼 진짜 앱(Xcode 없이, Command Line Tools만). iPhone 13 mini: PWA(홈 화면에 추가).
- 만드는 사람:
  - Claude Code: 2026-11-02까지만 사용 가능. 어려운 부분과 인수인계 파일을 맡는다.
  - Aside(Sonnet 5.5): 11-03부터 혼자 이어서 만든다. 브라우저 작업도 맡는다.

## 1. 절대 규칙
1. 0원. 결제 수단이나 카드 입력 화면이 나오면 즉시 멈추고 사용자에게 보고한다.
2. 비밀값은 ~/computer-use/.env에서만 읽는다. 코드·커밋·로그·화면에 키를 출력하지 않는다.
3. GitHub 토큰 "junbot-files"는 Regenerate·삭제하지 않는다. 필요하면 새 토큰을 만든다.
4. Hostless Redeploy 연타 금지(Cloudflare 1015 이력). 배포는 git push 한 번 하고 기다린다.
5. 공개 저장소에 올리기 전에 키처럼 생긴 문자열(gsk_, nvapi-, github_pat_, AIza, 봇 토큰 형식)을 검사하고, 발견되면 올리지 않고 멈춘다.
6. 기존 텔레그램 준봇(jun-server, @yjunphone_agent_bot)은 고장 내지 않는다. Haru 서버는 같은 봇 토큰으로 getUpdates를 절대 호출하지 않는다(409 충돌 이력). 알림 보내기(sendMessage)만 허용.
7. 지우기·보내기·결제는 어떤 모드에서도 사용자 허락 없이 하지 않는다.

## 2. 이미 있는 자산
- GitHub 계정 buriburiyj, gh CLI 로그인됨(맥).
- jun-server: 준봇(Hostless 워커 junbot, Groq). 유지.
- jun-lab: 공개, GitHub Actions 연구소, https://buriburiyj.github.io/jun-lab/
- jun-files: 비공개, Cloud Shell과 1분 자동 동기화.
- Hostless 무료: 계정 전체 0.5 vCPU / 1GiB RAM / 512MiB 디스크. 0.1 vCPU 워커가 CPU 경고를 두 번 받았다.
- Serv00: 신청 후 승인 대기 중.
- MacBook Air M4, Lima VM "box"(Codex CLI 로그인됨). Cloud Shell(주 50시간).
- 키: GROQ_API_KEY, NVIDIA_API_KEY(nvapi-), TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (~/computer-use/.env).

## 3. 구조
- 프론트: Vite + React + TypeScript PWA. 공개 저장소 buriburiyj/haru의 GitHub Pages로 배포. 주소는 https://buriburiyj.github.io/haru로 고정(패스키 때문에 바꾸지 않는다).
- 서버(가벼운 중계만): Python FastAPI, 메모리 150MB 이하. Hostless에 웹 앱으로 새로 만든다(기존 junbot 워커는 그대로 둔다). 답변은 SSE로 실시간 전송. CORS는 위 주소만 허용.
- 예비 서버: Serv00이 승인되면 같은 코드를 올린다. 한 번에 한 서버만 일하고(jun-files의 .agent/lease에 소유자와 만료 시각 기록), 다른 서버는 1분마다 확인하다가 만료되면 이어받는다.
- 무거운 작업(코드 실행, 문서 생성, 브라우저 조작): GitHub Actions.
  - 공개 작업: haru 저장소(무료 시간 사실상 무제한).
  - 개인 작업: jun-files(월 2,000분).
  - 맥이 켜져 있으면 box에서도 실행할 수 있다.
- 저장: jun-files/.agent/ 아래에 둔다.
    chats/ (대화 1개당 파일 1개), projects/, memory/ (주제별 파일), skills/, plugins/, connectors/ (설정만, 키는 제외), schedules/ (처음엔 비어 있음), permissions.json, index.json (검색용)
  - 답변 하나가 끝날 때 한 번에 커밋한다. 저장에 실패하면 서버에 보관했다가 다시 시도한다.

## 4. 모델 (자동 선택이 기본, 직접 선택도 가능)
- 쉽거나 어려운지 분류, 짧은 대화, 요약, Auto 모드 위험 검사: Groq
- 어려운 대화, 코딩, 계획: Codex. 0단계 시험 전 임시 순서는 gpt-6-luna → gpt-5.6-terra → gpt-5.6-luna. (6 Luna와 5.6 Terra는 0단계 시험으로 순서를 확정한다.)
- Codex 한도를 다 쓰면: NVIDIA nvidia/nemotron-3-ultra-550b-a55b → mistralai/mistral-large-4-1t-a52b → deepseek-ai/deepseek-v4.1-flash (분당 40회 제한)
- 사진: nvidia/nemotron-3.5-super-vl-120b-a12b
- 쓰지 않는 모델: kimi-k3, glm-5.2(410 종료), minimax-m3.1-flash, gpt-oss-20b(시간 초과)
- 다음 모델로 넘어가면 한 줄로 알린다. 429가 나면 잠깐 기다렸다가 다시 시도한다.
- 토큰 절약: 스킬·커넥터는 이름과 설명만 먼저 넣는다. 프로젝트 파일은 필요할 때만 읽는다. 긴 대화는 알아서 요약하고 이어 간다.

## 5. 화면 (Claude 앱 구조 그대로)
- 모드: Chat+Cowork를 하나로 합치고(최신 Claude 방식), Code는 따로 둔다.
- 사이드바: 새 대화, 검색(대화 내용 전체), 프로젝트, Scheduled, 대화 목록, 설정.
- 오른쪽에 아티팩트 창(코드·웹페이지·문서 미리보기). 폰에서는 탭하면 전체 화면.
- 생각 과정은 접어 두고 누르면 펼친다.
- 첫 화면: 빈 입력창과 인사 한 줄.
- 폰: 위쪽 메뉴로 모드 전환. ☰ 대화 목록, ✎ 새 대화.
- 입력창: 📎 파일·사진, + 메뉴(기억 끄기, 스타일, 모델), 🔧 커넥터·스킬 켜고 끄기.
- 테마: 시스템 설정을 따른다(밝게/어둡게).
- 스타일: 기본 / 간결 / 자세히.
- 넣지 않는 것: 음성(듣기·말하기 모두), 대화 공유 링크.
- 대화 기록은 사용자가 지울 때까지 보관.
- 시크릿 대화(유령 아이콘): 기록·기억에 남기지 않는다.

## 6. 기억 (Claude 방식)
- 대화 중에 주제별로 알아서 저장한다. "기억해"라고 하면 바로 저장한다.
- 저장할 때 "기억 업데이트됨" 표시를 띄우고, 누르면 내용이 보인다.
- 설정 → 기억에서 주제별로 보고 고치고 지울 수 있다.
- 프로젝트마다 기억을 따로 둔다. 다른 프로젝트 기억과 섞지 않는다.
- Chat에서 쌓인 기억은 Cowork·Code에서도 쓴다.

## 7. 권한
- 묻는 화면: [이번만 허용] [항상 허용] [거부]. 고른 것은 permissions.json에 기억한다. 설정 → 권한에서 취소할 수 있다.
- 지우기·보내기·결제는 "항상 허용"이어도 매번 묻는다.
- Code 모드 4개(Claude Code와 같음): Manual / 자동 수정 / Plan / Auto. 기본은 Auto(위험한 행동은 Groq가 검사하고, 지우기·보내기는 항상 묻는다).
- Plan 모드: 계획이 나오면 [자동으로 진행] [하나씩 승인] [계속 계획].
- 맥 화면 조작: 작업 시작할 때 한 번 묻고, "항상 허용"이면 다시 묻지 않는다.

## 8. 스킬·플러그인·커넥터
- 스킬: 폴더 하나에 SKILL.md(이름, 설명, 순서)와 선택적 스크립트. Claude 스킬 형식과 호환해서 공개된 Claude 스킬을 가져다 쓸 수 있게 한다.
- 스킬 자동 생성: 기본은 "만들기 전에 묻기". 설정에서 "알아서 만들기"로 바꿀 수 있고, 스킬마다 따로 정할 수도 있다.
- 플러그인: 스킬·커넥터·명령어 묶음. 한 번에 설치하고 한 번에 지운다.
- 커넥터: MCP 방식. 설정 → 커넥터 → [추가]로 계속 늘린다.
- 처음 붙일 커넥터:
  - Gmail: 앱 비밀번호(구글 2단계 인증 필요)
  - GitHub: 새 fine-grained 토큰
  - 구글 드라이브: OAuth. 시험 모드에서는 7일마다 다시 로그인해야 하는 문제가 있어서 만들 때 해결 방법을 정한다.
  - Notion: 내부 통합 토큰
- 로그인이 만료되면 "○○ 다시 연결해 주세요"라고 알린다.

## 9. 알림과 백그라운드
- 앱을 닫아도 서버와 Actions에서 계속 일하고, 끝나면 알린다.
- 알림: PWA 웹 푸시(iPhone에서는 홈 화면에 추가해야 받을 수 있다). 안 되면 텔레그램 sendMessage.
- 예약 작업과 먼저 말 걸기는 6단계에서 붙인다. 붙일 때 23시~07시는 조용히.

## 10. 보안
- 로그인: 패스키(Face ID·Touch ID). 예비 수단은 비밀번호와 GitHub 로그인.
- 서버 API는 로그인 세션 없이는 응답하지 않는다.
- 키는 서버 환경변수와 GitHub Secrets에만 둔다. 프론트로 절대 내려보내지 않는다.

## 11. 오류 처리
- 작업이 실패하면 방법을 바꿔서 3번까지 다시 해 보고, 그래도 안 되면 한 것과 막힌 곳을 보고한다.
- 서버가 죽으면 예비 서버가 1분 안에 이어받는다.
- 사용량 화면(설정 → 사용량): Codex 남은 한도, Groq 오늘 쓴 양, NVIDIA 분당 사용량, Actions 남은 분, Hostless CPU 경고.

## 12. 만드는 순서
- 0단계 시험: box에서 gpt-6-luna와 gpt-5.6-terra에게 같은 코딩 문제를 풀려 순서를 정한다. Codex 로그인을 GitHub Actions에서 쓸 수 있는지 시험하고, 안 되면 맥이 꺼져 있을 땐 NVIDIA가 맡는다.
- 0단계 뼈대: Hostless 서버, 모델 라우터, .agent 저장, 패스키, 빈 PWA.
- 1단계 Chat: 대화 목록·검색, SSE 답변, 수정·다시 생성, 파일·사진, 웹 검색(DuckDuckGo → Tavily, 출처 표시), 아티팩트, 프로젝트, 기억, 스타일, 모델 선택, 시크릿 대화.
- 2단계: 커넥터 4개와 권한 화면.
- 3단계 Code: 저장소 선택, 4개 모드, 계획 → 실행, 바뀐 부분 비교, 체크포인트 되돌리기, 실시간 터미널.
- 4단계 Cowork: 할 일 체크리스트, Word·PPT·Excel·PDF, 브라우저 조작.
- 5단계 맥 앱: Swift로 감싸기, 단축키, 파일 찾기, 화면 조작.
- 6단계: 예약 작업, 먼저 말 걸기, 스킬 자동 생성, Serv00 예비 서버.

## 13. 인수인계 (Claude Code는 반드시 11-02 안에)
- PROGRESS.md: 끝낸 일, 남은 일, 다음에 할 일 한 줄.
- STEPS.md: 남은 작업을 작은 단계로 쪼갠 목록. 단계마다 성공 확인 명령. Aside가 직접 실행하는 경우와 사용자가 맥 터미널에 붙여 넣는 경우 둘 다 되게 쓴다.
- 단계 하나가 끝날 때마다 git push하고 PROGRESS.md를 갱신한다.
- 시간이 모자라면 PWA보다 인수인계 파일을 먼저 끝낸다.
