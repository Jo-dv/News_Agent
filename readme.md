# 🚀 V3: ReAct 금융 뉴스 에이전트

정해진 순서대로 작동하던 선형(Linear) 파이프라인을 발전시켜, AI 스스로 정보의 충족 여부를 판단하고 목표를 달성할 때까지 능동적으로 재검색을 수행하는 ReAct 기반 에이전트입니다.

## ✨ 주요 기능 (Features)

1. **자율 탐색 루프 (ReAct Architecture)**
   - 에이전트가 검색 결과(Observation)를 대조하여, 목표한 금융 뉴스 데이터가 모두 수집되었는지 스스로 판단(Reasoning).
   - 누락된 정보가 있다면 해당 키워드로 검색 도구를 재호출(Action)하는 순환(Loop) 구조 구현.

2. **LangGraph 기반 순환 워크플로우 제어**
   - 조건부 엣지(Conditional Edges)를 활용하여 데이터 부족 시 검색 노드로 회귀하고, 목표 달성 시에만 리포트 생성 노드로 분기(Routing)하는 상태(State) 관리.

3. **프롬프트 모듈화 및 구조화된 리포트 생성**
   - 시스템 프롬프트와 템플릿을 별도 파일로 분리하여 코드 가독성 및 프롬프트 엔지니어링 효율 극대화.
   - 에이전트의 반복 추론 과정, 주간 핵심 요약, 주요 뉴스 상세 팩트, 출처 URL이 분리된 포맷으로 리포트 자동 작성 및 이메일 전송.

4. **디스코드 기반 RAG 챗봇**
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
* 하단 **[Scopes]** 에서 `bot`, `applications.commands` 체크 ➔ **[Bot Permissions]** 에서 필요한 권한(`Send Messages`, `Read Messages/View Channels` 등) 체크
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
!리포트생성: 에이전트가 ReAct 루프를 가동하여 정보 수집, 리포트 생성, DB 적재 및 이메일 발송을 순차적으로 실행합니다.

!종료: 시스템 종료 명령을 접수하고 봇과 도커 컨테이너를 안전하게 종료합니다.

[일반 채팅 입력]: 리포트 생성이 완료된 후 질문을 입력하면, 저장된 벡터 DB 문서를 기반으로 답변을 생성합니다(RAG).

## 📁 파일 구조 (File Structure)
```
.
├── app/
│   ├── main.py         # 디스코드 봇 인터페이스, 슬래시 명령어 및 파이프라인 실행
│   ├── agent.py        # LangGraph ReAct 워크플로우(루프 및 분기), 노드, DB 세팅
│   ├── prompts.py      # LLM 프롬프트 템플릿 분리 관리 모듈
│   └── email_sender.py # 이메일(SMTP) 발송 모듈
├── chroma_data/        # ChromaDB 벡터 데이터 저장 폴더
├── .env                # API 키 설정 파일 (git 제외)
├── docker-compose.yml  # 도커 컴포즈 설정
├── Dockerfile          # 도커 이미지 빌드 파일
└── requirements.txt    # 파이썬 패키지 목록
```