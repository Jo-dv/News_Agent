import requests
import time

def test_raw_api():
    print("="*50)
    print("⚡ [순수 API 테스트] Ollama 직접 호출 중...")
    
    start_time = time.time()
    
    try:
        res = requests.post(
            "http://ollama:11434/api/generate", # 👈 ollama 대신 다시 localhost로 변경!
            json={
                "model": "coolsoon/kanana-1.5-8b", # 👈 무거운 kanana를 버리고 3B 모델로 교체!
                "prompt": "한국어로 AI를 3줄로 설명해줘.",
                "stream": False
            },
            timeout=300 
        )
        res.raise_for_status()
        
        end_time = time.time()
        
        print("\n🎉 [응답 결과]")
        print(res.json()["response"])
        print("="*50)
        print(f"⏱️ 소요 시간: {end_time - start_time:.1f}초")
        
    except Exception as e:
        print(f"❌ API 호출 실패: {e}")

if __name__ == "__main__":
    test_raw_api()