import requests
from bs4 import BeautifulSoup
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def get_target_news(max_items=10):
    url = "https://www.mk.co.kr/news/financial/financial-policy"
    headers = {"User-Agent": "Mozilla/5.0"}
    print("\n[수집] '매일경제 금융정책' 최신 기사 크롤링 시작...")
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"[에러] 웹페이지 접속 실패: {e}")
        return []
        
    soup = BeautifulSoup(response.text, 'html.parser')
    target_news = []
    seen_links = set()
    
    for a_tag in soup.find_all('a', href=True):
        link = a_tag['href']
        if '/news/' in link and re.search(r'\d{7,}', link):
            if link.startswith('/'):
                link = "https://www.mk.co.kr" + link
                
            if link not in seen_links:
                # [정제 1] 짬뽕 텍스트 방지: 진짜 제목 태그만 핀셋으로 추출
                title_element = a_tag.select_one('.news_ttl, .tit, .title, h3, h4, strong')
                
                if title_element:
                    title = title_element.get_text(strip=True)
                else:
                    title = a_tag.get_text(separator='\n', strip=True).split('\n')[0]
                
                if len(title) > 8:
                    seen_links.add(link)
                    target_news.append({"title": title, "link": link})
                    
            if len(target_news) >= max_items:
                break
                
    print(f"기사 {len(target_news)}개 링크 수집 완료!")
    return target_news

def extract_content(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # [정제 2] 인터랙티브/특수 기사 원천 차단 (입구컷)
        if soup.select_one('[class*="mvr-"], [class*="interact"], .story_wrap, .view_special, iframe[src*="interactive"]'):
            print(f"[스킵] 인터랙티브/특수 기사 제외: {url}")
            return ""
            
        # 기사 본문 영역 찾기
        content_area = soup.select_one('div[itemprop="articleBody"]')
        if not content_area:
            content_area = soup.select_one('.news_cnt_detail_wrap')
            
        if not content_area:
            return ""

        # [정제 3] 불필요한 쓰레기 태그(사진확대 등) 사전 제거
        for s in content_area(['script', 'style', 'iframe', 'figcaption', 'figure']):
            s.extract()
            
        for zoom_btn in content_area.select('.btn_zoom, .img_zoom, .img_desc'):
            zoom_btn.extract()

        # [정제 4] 중간제목(midtitle_text) 보호: 내부 이중개행 원천 봉쇄
        for midtitle in content_area.select('.midtitle_text'):
            clean_text = midtitle.get_text(separator=' ', strip=True)
            midtitle.string = f"[{clean_text}]"

        # [정제 5] 최상단 요약문(서브타이틀) 분리
        summary_text = ""
        summary_el = content_area.select_one('.summary, .sub_tit, .news_summary, ul')
        if summary_el:
            summary_text = summary_el.get_text(separator=' ', strip=True)
            summary_el.extract()

        # 본문 텍스트 추출 
        body_text = content_area.get_text(separator='\n', strip=True)
        
        # [정제 6] 정밀 후처리 (꼬리표 제거 및 문단 정렬)
        body_text = body_text.replace('사진확대', '')
        body_text = re.sub(r'\[[^\]]*기자[^\]]*\]', '', body_text)
        
        # 엔터 1번 이상을 전부 엔터 2번(\n\n)으로 변경하여 가독성 극대화
        body_text = re.sub(r'\n+', '\n\n', body_text)

        # 최종 텍스트 조립: [요약문] + (줄바꿈 2번) + [본문]
        final_text = ""
        if summary_text:
            final_text += f"[핵심 요약]\n{summary_text}\n\n"
        final_text += body_text.strip()

        return final_text
        
    except Exception as e:
        print(f"[본문 추출 에러] {url}: {e}")
        return ""

def filter_duplicate_news(news_list, similarity_threshold=0.6):
    print(f"\n[전처리] 총 {len(news_list)}개의 기사 본문을 분석하여 중복 및 범위 외 기사를 제거합니다...")
    valid_news = []
    contents = []
    
    for news in news_list:
        content = extract_content(news['link'])
        
        # [정제 7] 텍스트 길이가 300자 미만이면 불량 기사(인터랙티브, 포토 등)로 간주하고 폐기
        if len(content) > 300: 
            news['content'] = content
            valid_news.append(news)
            contents.append(content)
            
    if not contents:
        return []

    # TF-IDF 기반 코사인 유사도 중복 검사
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(contents)
    cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)
    
    unique_news = []
    seen_indices = set()
    
    for i in range(len(valid_news)):
        if i in seen_indices:
            continue
        unique_news.append(valid_news[i])
        for j in range(i + 1, len(valid_news)):
            if cosine_sim[i][j] >= similarity_threshold:
                seen_indices.add(j) 
                
    print(f"최종 분석 대상 기사: {len(unique_news)}개 (범위 외/중복 {len(news_list) - len(unique_news)}개 제거)")
    return unique_news