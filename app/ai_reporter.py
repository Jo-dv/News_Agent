from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOllama(
    model="coolsoon/kanana-1.5-8b", 
    base_url="http://ollama:11434",
    temperature=0.1 
)

from langchain_core.prompts import ChatPromptTemplate

def generate_daily_report(news_list):
    print("\n[AI 분석] 카나나 모델이 인사이트 리포트를 작성합니다...")
    
    news_text_block = ""
    dynamic_article_template = "" # 동적 템플릿 변수 추가
    
    # 1. 뉴스 데이터와 출력 템플릿을 기사 개수만큼 동시에 조립합니다.
    for i, news in enumerate(news_list, 1):
        news_text_block += f"[기사 {i}]\n제목: {news['title']}\n링크: {news['link']}\n본문: {news['content'][:400]}...\n\n"
        
        dynamic_article_template += f"▶ [기사 {i}] (기사 {i} 원문 제목)\n- (기사 {i} 핵심 요약 1)\n- (기사 {i} 핵심 요약 2)\n🔗 원문 링크: {news['link']}\n\n"

    prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 최고 수준의 테크/비즈니스 수석 애널리스트입니다. 
주어진 최신 뉴스 기사들을 분석하여 '전문적이고 가독성 높은 이메일 브리핑 리포트'를 작성하세요.

[엄격한 절대 규칙]
1. 누락 금지: [출력 템플릿]에 제시된 모든 [기사 N] 항목을 빠짐없이 채워 넣으세요.
2. 메타 발언 금지: 리포트의 시작이나 끝에 인사말, 부연 설명을 절대 기재하지 마세요. 양식의 내용만 출력하고 즉시 종료하세요.
3. 용어 사전 엄격 제한: 기사 내에 포함된 난해한 금융/기술 전문 용어만 최대 3개 이내로 추출하세요. '투자', '수출', '지원', '강화' 등 일반적인 단어는 절대 포함하지 마세요. 추출할 만한 어려운 단어가 없으면 내용에 "해당 사항 없음" 딱 한 줄만 출력하세요."""),
        
        ("human", """
오늘의 리포트 주제: 매일경제 금융정책 동향

[뉴스 데이터]
{news_data}

위 데이터를 바탕으로 아래 [출력 템플릿]의 구조와 기호를 그대로 사용하여 리포트를 작성하세요. 

[출력 템플릿]
=========================================
 📈 [매일경제 금융정책] 일일 동향 브리핑
=========================================

■ 1. 오늘의 핵심 요약 (제공된 기사 내용만으로 유동적 요약)
- 

-----------------------------------------
■ 2. 주요 뉴스 상세

{dynamic_template}
-----------------------------------------
■ 3. 애널리스트 인사이트 (시장/산업 트렌드 분석)
- 
- 

-----------------------------------------
■ 4. 주요 용어 사전 (최대 3개, 일반 단어 금지)
- 
""")
    ])

    chain = prompt | llm
    
    try:
        # 조립된 동적 템플릿을 프롬프트 변수에 함께 전달합니다.
        response = chain.invoke({
            "news_data": news_text_block,
            "dynamic_template": dynamic_article_template.strip()
        })
        print("[분석 완료] 리포트 생성 완료!")
        return response.content
    except Exception as e:
        print(f"[에러] 리포트 생성 실패: {e}")
        return None