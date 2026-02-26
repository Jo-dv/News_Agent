from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOllama(
    model="coolsoon/kanana-1.5-8b", # 현재 쌩쌩하게 돌아가는 모델명 유지
    base_url="http://ollama:11434",
    temperature=0.1 
)

def generate_daily_report(news_list):
    print("\n[AI 분석] 카나나 모델이 인사이트 리포트를 작성합니다...")
    
    news_text_block = ""
    for i, news in enumerate(news_list, 1):
        # 👈 본문뿐만 아니라 '링크' 정보도 LLM에게 같이 넘겨줍니다!
        news_text_block += f"[기사 {i}]\n제목: {news['title']}\n링크: {news['link']}\n본문: {news['content'][:400]}...\n\n"

    # 👈 시스템 프롬프트에 '절대 하지 말아야 할 3가지 규칙'을 강력하게 추가합니다.
    prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 최고 수준의 테크/비즈니스 수석 애널리스트입니다. 
주어진 최신 뉴스 기사들을 분석하여 '전문적이고 명확한 일일 리포트'를 작성해야 합니다. 
반드시 한국어로 작성하며, 다음 규칙을 엄격하게 지키세요.

[엄격한 규칙]
1. 리포트 전체에 이모지(emoji)를 절대 사용하지 마세요. 오직 텍스트만 사용하세요.
2. 리포트 마지막에 '위 분석은 바탕으로...', '문의해 주세요' 등의 맺음말이나 안내문을 절대 쓰지 마세요. 지정된 양식만 출력하고 바로 답변을 종료하세요.
3. '주요 뉴스 상세' 항목에서는 각 기사의 요약이 끝난 후, 다음 줄에 반드시 제공된 [원문 링크]를 그대로 기재하세요."""),
        
        ("human", """
오늘의 리포트 주제: 매일경제 금융정책 동향

[뉴스 데이터]
{news_data}

위 뉴스들을 종합하여 아래 양식에 맞게 마크다운 포맷으로 작성해 주세요.

# [매일경제 금융정책] 일일 동향 브리핑
## 1. 오늘의 핵심 요약 (3줄)
## 2. 주요 뉴스 상세 (각 기사별 핵심 요약 및 하단에 원문 링크 기재)
## 3. 애널리스트 인사이트 (향후 시장/산업 트렌드 분석)
## 4. 주요 용어 사전 (어려운 단어 2~3개 설명)
""")
    ])

    chain = prompt | llm
    
    try:
        response = chain.invoke({"news_data": news_text_block})
        print("[분석 완료] 리포트 생성 완료!")
        return response.content
    except Exception as e:
        print(f"[에러] 리포트 생성 실패: {e}")
        return None