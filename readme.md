# 🚀 V2: LLM 기반 지능형 금융 뉴스 파이프라인 (LangGraph Chain)

단순 웹 스크래핑의 한계를 극복하기 위해, 검색 API(Tavily)와 대형 언어 모델(LLM)의 추론 능력을 결합한 지능형 데이터 파이프라인입니다. 수집된 데이터를 통해 인사이트 리포트를 생성하며, 디스코드 봇을 통해 벡터 DB 기반 질의응답(RAG)을 수행할 수 있습니다.

## ✨ 주요 기능 (Features)

1. **동적 검색 및 LLM 필터링 (Reasoning)**
   - 고정된 웹페이지 스크래핑 대신 Tavily Search API를 사용하여 '최근 1주일' 기사를 동적으로 탐색.
   - LLM이 검색된 raw 데이터를 읽고, 과거 데이터나 무의미한 기사를 스스로 폐기하여 핵심 이슈 5가지만 추출.

2. **LangGraph 기반 선형 워크플로우 제어**
   - `검색 노드` ➔ `리포트 생성 노드` ➔ `DB 저장 노드`로 이어지는 파이프라인을 LangGraph의 StateGraph로 구조화하여 안정적으로 상태(State) 관리.

3. **구조화된 템플릿 리포트 생성 및 이메일 발송**
   - 에이전트의 추론 과정, 주간 핵심 요약, 5대 주요 뉴스 상세 팩트, 출처 URL이 분리된 포맷으로 리포트 자동 작성 및 이메일 전송.

4. **디스코드 봇 인터랙션 및 RAG 챗봇**
   - 매일 생성된 리포트를 ChromaDB(벡터 데이터베이스)에 임베딩하여 저장.
   - 디스코드 채팅을 통해 명령어를 제어하고, DB에 저장된 과거 리포트를 기반으로 팩트 중심의 질의응답(RAG) 수행.

## 🛠 기술 스택 (Tech Stack)
- **Language:** Python 3.11
- **Framework:** LangChain, LangGraph
- **LLM & Embedding:** OpenAI GPT (`gpt-5.4-mini`, `text-embedding-3-small`)
- **Vector Database:** ChromaDB
- **Search API:** Tavily Search API
- **Interface:** Discord.py

## 🤖 디스코드 봇 세팅 가이드
[Discord Developer Portal](https://discord.com/developers/applications) 접속 후 다음 3단계를 진행하십시오.

**1. 봇 생성 및 토큰 발급**
* **[New Application]** 생성 ➔ 좌측 **[Bot]** 메뉴 이동
* **[Reset Token]** 클릭 ➔ 발급된 토큰 복사 ➔ `.env` 파일의 `DISCORD_BOT_TOKEN`에 붙여넣기

**2. 필수 메시지 읽기 권한(Intent) 허용**
* 동일한 **[Bot]** 메뉴 하단 스크롤 ➔ **[Privileged Gateway Intents]** 섹션 확인
* **[Message Content Intent]** 활성화(토글 ON) ➔ **[Save Changes]** 저장

**3. 봇 초대 링크 생성 및 서버 추가**
* 좌측 **[OAuth2]** 메뉴 이동
* 하단 **[Scopes]** 에서 `bot` 체크 ➔ **[Bot Permissions]** 에서 필요한 권한(`Send Messages`, `Read Messages/View Channels` 등) 체크
* 하단에 생성된 URL 복사 ➔ 웹 브라우저 주소창에 입력하여 내 서버로 초대

## 💾 환경 변수 설정 (.env)
루트 디렉토리에 `.env` 파일을 생성하고 아래 API 키를 입력하십시오.
```env
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
DISCORD_BOT_TOKEN=...
SENDER_EMAIL=발신용_구글이메일@gmail.com
SENDER_PASSWORD=구글앱비밀번호
RECEIVER_EMAIL=수신용_이메일@gmail.com
```

## 💬 디스코드 명령어 (Discord Commands)
!리포트생성: 파이프라인을 가동하여 기사 검색, 리포트 생성, DB 적재 및 이메일 발송을 순차적으로 실행합니다.

!종료: 시스템 종료 명령을 접수하고 봇과 도커 컨테이너를 안전하게 종료합니다.

[일반 채팅 입력]: 리포트 생성이 완료된 후 질문을 입력하면, 저장된 벡터 DB 문서를 기반으로 답변을 생성합니다(RAG).

## 📁 파일 구조 (File Structure)
```
.
├── app/
│   ├── main.py         # 디스코드 봇 인터페이스 및 비동기 파이프라인 실행
│   ├── agent.py        # LangGraph 워크플로우, 노드 함수(검색, 생성, RAG), DB 세팅
│   └── email_sender.py # 이메일(SMTP) 발송 모듈
├── chroma_data/        # ChromaDB 벡터 데이터 저장 폴더
├── .env                # API 키 설정 파일 (git 제외)
├── docker-compose.yml  # 도커 컴포즈 설정
├── Dockerfile          # 도커 이미지 빌드 파일
└── requirements.txt    # 파이썬 패키지 목록
```