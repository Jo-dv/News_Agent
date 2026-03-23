from news_scraper import get_target_news, filter_duplicate_news
from ai_reporter import generate_daily_report
from notion_db import save_to_notion
from email_sender import send_report_email
import time

def run_agent():
    print("="*50)
    print("[AI 뉴스 에이전트] 일일 배치 작업을 시작합니다...")
    print("="*50)
    
    # 1. 크롤링
    news_list = get_target_news(max_items=10)
    if not news_list:
        return
        
    # 2. 중복 제거
    filtered_news = filter_duplicate_news(news_list, similarity_threshold=0.6)
    
    # 💡 [NEW] 3. 필터링된 원본 데이터를 노션에 영구 아카이빙
    top_news = filtered_news
    save_to_notion(top_news)
    
    # 4. AI 리포트 작성
    start_time = time.time()
    final_report = generate_daily_report(top_news[:3])
    end_time = time.time()
    total_time = end_time - start_time
    
    if final_report:
        print(f"\nAI 요약 소요 시간: {total_time // 60}분 {total_time % 60:.1f}초")
        
        # 💡 [NEW] 5. 완성된 리포트를 이메일로 쏘기
        send_report_email(final_report)
        
        print("\n모든 에이전트 작업이 성공적으로 종료되었습니다.")

if __name__ == "__main__":
    run_agent()