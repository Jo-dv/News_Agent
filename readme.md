# 🚀 AI Financial News Agent (AI 금융 뉴스 자동화 에이전트)

매일 아침 '매일경제 금융정책' 뉴스를 자동으로 수집하고, AI가 핵심만 요약하여 노션(Notion)에 아카이빙한 뒤 이메일로 브리핑 리포트를 발송해 주는 자율형 데이터 파이프라인입니다.

## ✨ 주요 기능 (Features)

1. **지능형 웹 크롤링 & 데이터 정제**
   - 매일경제 [금융정책 섹션](https://www.mk.co.kr/news/financial/financial-policy) 최신 기사 자동 수집
   - 스크롤/인터랙티브 특수 기사(`mvr-`, `interact` 등) 원천 차단
   - 300자 미만 깡통 기사 필터링 및 기자 이름 꼬리표 제거
   - 가독성 극대화를 위한 문단 정규화 및 중간제목(`midtitle`) 보호
2. **AI 기반 중복 기사 제거**
   - TF-IDF 및 코사인 유사도(Cosine Similarity)를 활용하여 내용이 겹치는 기사 자동 병합/제거
3. **노션(Notion) 자동 아카이빙**
   - 정제된 원본 기사를 지정된 노션 데이터베이스에 영구 보존
4. **LLM 기반 핵심 브리핑 생성**
   - 수집된 주요 기사들을 AI가 분석하여 일일 금융 브리핑 리포트 작성
5. **이메일(SMTP) 자동 발송**
   - 완성된 브리핑 리포트를 이메일로 자동 전송

## 🛠 기술 스택 (Tech Stack)
- **OS:** Window 10
- **Language:** Python 3.11
- **Environment:** Docker, Docker Compose
- **Libraries:** `requests`, `beautifulsoup4`, `scikit-learn`, `langchain-core`, `langchain_ollama`, `python-dotenv`
- **External API:** Notion API, Google Gmail SMTP

# 환경 변수
[노션 DB 토큰 설정하기](https://www.notion.so/profile/integrations/internal)  
[앱 비밀번호 설정하기](https://support.google.com/accounts/answer/185833?hl=ko)
```
# Notion API 설정
NOTION_TOKEN=secret_노션토큰
NOTION_DATABASE_ID=32자리데이터베이스ID

# Gmail 이메일 발송 설정
SENDER_EMAIL=구글이메일@gmail.com
SENDER_PASSWORD=구글앱비밀번호입력
RECEIVER_EMAIL= # 필요시
```

# ⚙️ 설치 및 세팅 방법 (Installation & Setup)
[도커 설치](https://www.docker.com/)
```bash
git clone https://github.com/Jo-dv/News_Agent.git
```

```
docker-compose up --build -d  # 컨테이너 일괄 실행
docker exec -it agent_ollama ollama pull coolsoon/kanana-1.5-8b  # 모델 설치
docker exec -it agent_app python main.py  # 에이전트 실행
```

# 로컬 LLM
## kanana-1.5-8b-instruct-2505 
https://huggingface.co/kakaocorp/kanana-1.5-8b-instruct-2505  
https://ollama.com/coolsoon/kanana-1.5-8b


# 파일구조
```
.
├── app/
│   ├── main.py             # 메인 파이프라인 실행 스크립트
│   ├── news_scraper.py     # 웹 크롤링 및 데이터 전처리 모듈
│   ├── ai_reporter.py      # LLM 연동 및 리포트 생성 모듈
│   ├── notion_db.py        # 노션 API 연동 및 아카이빙 모듈
│   └── email_sender.py     # 이메일 전송 모듈
├── .env                    # 환경변수
├── .gitignore              
├── docker-compose.yml      # 도커 컴포즈 설정
├── Dockerfile              # 도커 이미지 빌드 파일
└── requirements.txt        # 파이썬 의존성 패키지 목록
```