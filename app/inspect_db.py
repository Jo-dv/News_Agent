import chromadb

# 1. 새로 분리한 V2 DB 경로 지정
client = chromadb.PersistentClient(path="./chroma_data")

# 2. 컬렉션(테이블) 가져오기
try:
    collection = client.get_collection(name="financial_reports")
except ValueError:
    print("🚨 'financial_reports' 컬렉션이 존재하지 않습니다. 아직 데이터가 한 번도 저장되지 않았습니다.")
    exit()

# 3. 전체 데이터 개수 확인
count = collection.count()
print(f"--- 현재 DB에 저장된 총 문서 수: {count}개 ---\n")

if count == 0:
    print("데이터가 0개입니다. agent.py의 rag_store_node가 정상적으로 실행되지 않았거나 에러가 났습니다.")
    exit()

# 4. 최근 저장된 데이터 5개 확인 (임베딩 값은 빼고 원문과 메타데이터만 출력)
results = collection.peek(limit=5)

for i, (doc, meta) in enumerate(zip(results['documents'], results['metadatas'])):
    print(f"[{i+1}] 메타데이터: {meta}")
    print(f"원문 내용 (앞 300자): {doc[:300]}...\n")
    print("-" * 50)