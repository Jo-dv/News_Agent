import requests
import datetime
import os
from dotenv import load_dotenv

# .env 파일에서 환경변수를 불러옵니다.
load_dotenv()

# os.getenv()를 사용해 안전하게 값을 가져옵니다.
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def save_to_notion(news_list):
    print("\n[DB 저장] 노션 데이터베이스에 기사를 아카이빙합니다...")
    
    # 환경변수 로드 실패 시 강제 종료 (안전장치)
    if not NOTION_TOKEN or not DATABASE_ID:
        print("[에러] 노션 토큰이나 DB ID가 없습니다. .env 파일을 다시 확인해 주세요.")
        return

    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    success_count = 0
    
    for news in news_list:
        url = "https://api.notion.com/v1/pages"
        
        # 기사 본문이 너무 길면 노션 API가 튕겨내므로 1900자로 자릅니다.
        content_safe = news['content'][:1900] + ("..." if len(news['content']) > 1900 else "")
        
        payload = {
            "parent": {"database_id": DATABASE_ID},
            "properties": {
                # 노션 표의 실제 이름과 띄어쓰기까지 100% 똑같아야 합니다!
                "기사 제목": {"title": [{"text": {"content": news['title']}}]},
                "일자": {"date": {"start": today_str}},
                "원문 링크": {"url": news['link']}
            },
            # 기사 원문은 페이지 클릭 시 나타나는 '본문 블록'에 넣습니다.
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": content_safe}}]
                    }
                }
            ]
        }
        
        try:
            res = requests.post(url, headers=headers, json=payload)
            res.raise_for_status()
            success_count += 1
            
        except requests.exceptions.HTTPError as e:
            # 노션이 뱉어내는 '진짜 상세 에러 메시지'를 가로채서 출력합니다.
            print(f"[노션 에러] {news['title'][:10]}... 저장 실패!")
            print(f"↳ 상세 이유: {e.response.text}")
            
        except Exception as e:
            print(f"[알 수 없는 에러] {news['title'][:10]}... 저장 실패: {e}")
            
    # 최종 결과 출력
    if success_count > 0:
        print(f"총 {success_count}개의 기사가 노션에 성공적으로 저장되었습니다!")
    else:
        print("노션 저장에 모두 실패했습니다. 위 상세 에러 메시지를 확인해 주세요.")