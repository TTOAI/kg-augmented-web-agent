## 1. RDF/OWL/SPARQL 예제로 실제 KG를 손으로 읽는 법

핵심은 이것입니다.
KG를 읽을 때는 **RDF는 사실을 적는 층**, **OWL/RDFS는 그 사실에 의미와 추론 규칙을 붙이는 층**, **SPARQL은 그 그래프를 질의하는 층**으로 보면 됩니다. RDF는 주어-술어-목적어 트리플로 그래프를 만들고, OWL 2는 classes, properties, individuals를 더 풍부하게 표현하며, SPARQL은 RDF 그래프에 대해 triple pattern, OPTIONAL, UNION, property paths 같은 방식으로 질의합니다. ([W3C][1])

먼저 아주 작은 예제를 보자. 아래 코드는 **설명용 예시**다.

```turtle
@prefix ex:   <http://example.org/> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

ex:Seoul a ex:City ;
    ex:capitalOf ex:SouthKorea ;
    ex:population "9500000"^^xsd:integer .

ex:SouthKorea a ex:Country .

ex:capitalOf a owl:ObjectProperty ;
    rdfs:domain ex:City ;
    rdfs:range ex:Country ;
    owl:inverseOf ex:hasCapital .

ex:hasCapital a owl:ObjectProperty .
```

이걸 읽는 순서는 늘 비슷합니다.

### 1-1. 먼저 “문장”이 아니라 “트리플”로 쪼개서 본다

RDF의 기본 단위는 트리플이다. 그래서 위 Turtle 문법을 볼 때도 머릿속에서는 다음처럼 풀어서 읽어야 한다. `a`는 Turtle에서 `rdf:type`의 축약형이고, 세미콜론 `;`은 같은 주어를 반복하지 않는 약기법이다. 즉 위 예시는 실제로는 `ex:Seoul rdf:type ex:City`, `ex:Seoul ex:capitalOf ex:SouthKorea`, `ex:Seoul ex:population "9500000"^^xsd:integer` 같은 여러 개의 트리플로 해석된다. Turtle은 RDF 그래프를 더 compact하게 쓰기 위한 텍스트 문법이다. ([W3C][2])

그래서 첫 번째 읽기 결과는 아주 단순하다.

- `Seoul`은 `City`다.
- `Seoul`은 `SouthKorea`의 수도다.
- `Seoul`의 population은 정수형 9500000이다.
- `SouthKorea`는 `Country`다. ([W3C][1])

### 1-2. 그다음 “사실”과 “스키마/의미”를 분리해서 본다

위 예제에서 `ex:Seoul ex:capitalOf ex:SouthKorea` 같은 것은 **개별 사실(ABox에 가까운 층)**이고, `ex:capitalOf rdfs:domain ex:City`, `rdfs:range ex:Country`, `owl:inverseOf ex:hasCapital` 같은 것은 **어휘와 의미를 규정하는 층(TBox에 가까운 층)**으로 보는 것이 이해에 좋다. RDFS는 class, property, domain, range 같은 기본 어휘를 제공하고, OWL 2는 properties, classes, individuals를 더 정교하게 기술하며 RDF와 함께 사용될 수 있다. ([W3C][3])

이 구분이 중요한 이유는, KG에서 항상 **“명시된 것(explicit)”**과 **“의미상 따라오는 것(inferred)”**이 다르기 때문이다. 위 그래프에 명시적으로 적힌 것은 `Seoul capitalOf SouthKorea`이지, `SouthKorea hasCapital Seoul`은 아니다. 하지만 `owl:inverseOf`가 있으므로 OWL 의미론을 쓰면 뒤의 사실을 **추론 가능**하다고 볼 수 있다. SPARQL도 simple entailment만 볼지, RDF/RDFS/OWL entailment를 볼지에 따라 결과가 달라질 수 있다. W3C의 SPARQL Entailment Regimes는 바로 이 차이를 다룬다. ([W3C][4])

### 1-3. domain/range는 “검증 규칙”이라기보다 “의미 단서”로 읽는다

많이 헷갈리는 부분인데, RDFS의 `domain`과 `range`는 관계형 DB의 강한 타입 제약처럼만 읽으면 안 된다. 예를 들어 `capitalOf`의 domain이 `City`, range가 `Country`라면, 어떤 트리플이 `X capitalOf Y`로 나타났을 때 RDFS 의미론 아래에서는 `X`가 `City`, `Y`가 `Country`라는 해석이 가능해진다. 즉 이것은 단지 금지/허용 제약이라기보다 **분류와 추론에 쓰이는 의미 정보**다. ([W3C][1])

그래서 위 예제에서는 이미 `Seoul a City`, `SouthKorea a Country`를 명시해 두었지만, 극단적으로는 그 타입 선언이 없더라도 `capitalOf`의 domain/range만으로 비슷한 타입 해석이 가능하다. 이때부터 KG 읽기는 단순 문자열 읽기가 아니라 **관계가 엔터티의 종류를 규정하는 읽기**가 된다. ([W3C][1])

### 1-4. OWL은 “관계의 의미”를 더 강하게 만든다

RDF만 보면 “연결돼 있다” 수준이고, RDFS를 얹으면 “어떤 종류의 연결인지”가 보인다. OWL까지 가면 “그 연결이 어떤 논리적 성질을 가지는지”를 더 강하게 표현할 수 있다. OWL 2는 classes, properties, individuals뿐 아니라 더 풍부한 공리와 프로파일을 제공한다. 대표적으로 `owl:inverseOf`는 한 관계의 역관계를 정의한다. 그래서 `capitalOf`와 `hasCapital`을 읽을 때는 “서로 반대 방향으로 같은 사실을 말한다”라고 해석하면 된다. ([W3C][3])

실전에서 OWL을 읽을 때는 우선 다음 성질이 보이면 체크하면 된다.

- `owl:inverseOf`: 역관계
- `owl:equivalentClass`: 동치 클래스
- `owl:subClassOf`: 상위/하위 분류
- `owl:Restriction`: 어떤 속성을 반드시/일부 가져야 하는 조건

이 네 가지가 보이면 “아, 이 KG는 단순 연결 그래프가 아니라 **추론 가능한 의미 그래프**구나”라고 보면 된다. OWL 2 Primer는 이런 구성요소를 소개하는 대표 문서다. ([W3C][3])

## 2. SPARQL은 어떻게 손으로 읽나

SPARQL은 어렵게 느껴지지만, 기본은 **“변수가 들어간 트리플 패턴 매칭”**이다. W3C 문서도 SPARQL이 RDF 그래프에 대해 required pattern, optional pattern, disjunction, filters 등을 표현한다고 설명한다. ([W3C][5])

예를 들어:

```sparql
PREFIX ex: <http://example.org/>

SELECT ?country
WHERE {
  ex:Seoul ex:capitalOf ?country .
}
```

이 질의는 “주어가 Seoul이고 술어가 capitalOf인 트리플에서 목적어를 찾아라”라는 뜻이다. 위 예제 그래프에서는 `?country = ex:SouthKorea`가 된다. 이건 **명시된 트리플**만 봐도 바로 풀린다. ([W3C][5])

반면 이런 질의를 보자.

```sparql
PREFIX ex: <http://example.org/>

SELECT ?city
WHERE {
  ex:SouthKorea ex:hasCapital ?city .
}
```

이 질의는 **해당 트리플이 그래프에 명시되어 있느냐**에 따라 결과가 달라진다. 지금 예제에는 `SouthKorea hasCapital Seoul`가 직접 적혀 있지 않으므로, **simple entailment**로만 보면 결과가 없을 수 있다. 하지만 `capitalOf owl:inverseOf hasCapital`를 반영하는 entailment regime이라면 `?city = ex:Seoul`을 얻을 수 있다. 즉 SPARQL을 읽을 때는 항상 “이 엔드포인트가 추론을 켠 상태인가?”를 같이 봐야 한다. ([W3C][4])

또 SPARQL에서 자주 나오는 `OPTIONAL`은 “있으면 붙이고, 없어도 기본 매치는 유지하라”는 뜻이다.

```sparql
PREFIX ex: <http://example.org/>

SELECT ?city ?population
WHERE {
  ?city a ex:City .
  OPTIONAL { ?city ex:population ?population . }
}
```

이 질의는 모든 `City`를 찾되, 인구 정보가 있으면 같이 보여주라는 뜻이다. W3C 문서에서 OPTIONAL은 required graph pattern에 optional graph pattern을 결합하는 핵심 구성으로 설명된다. ([W3C][6])

그리고 **property paths**를 보면 “여러 단계 관계를 타고 가는 질의”라고 읽으면 된다. SPARQL 1.1은 property paths를 도입해 arbitrary-length path 표현을 지원했다. ([W3C][7])

## 3. 실제로 KG를 손으로 읽을 때의 체크리스트

실전에서는 아래 순서가 가장 안전하다.

첫째, **어떤 노드가 엔터티고 어떤 노드가 클래스인지** 본다. `rdf:type`이나 `a`가 가장 빠른 힌트다. RDF 그래프의 주체와 객체는 IRI, blank node, literal 등이 될 수 있고, 타입 선언은 엔터티의 역할을 드러내는 가장 직접적인 표지다. ([W3C][1])

둘째, **사실 트리플과 스키마 트리플을 분리한다**. `Seoul capitalOf SouthKorea`는 사실, `capitalOf rdfs:domain City`는 스키마다. 이 둘을 섞어서 읽으면 금방 헷갈린다. RDFS와 OWL은 바로 이 스키마·의미 계층을 위한 언어다. ([W3C][3])

셋째, **명시 사실과 추론 가능 사실을 구분한다**. 특히 inverse, subclass, equivalentClass, restriction이 있으면 “직접 적혀 있지 않아도 따라올 수 있는 사실”이 생긴다. 하지만 실제 질의 결과는 엔드포인트의 entailment 지원 여부에 따라 달라진다. ([W3C][4])

넷째, **SPARQL은 자연어 문장이 아니라 그래프 패턴 매칭이라고 생각한다**. `SELECT`는 무엇을 꺼낼지, `WHERE`는 어떤 패턴을 만족하는 노드를 찾을지 적는 부분이다. OPTIONAL, UNION, FILTER, property paths는 그 패턴을 더 유연하게 만드는 장치다. ([W3C][5])

이 네 단계만 지켜도 RDF/OWL/SPARQL 문서를 읽을 때 훨씬 덜 막힌다.

## 4. LLM + KG 시스템 아키텍처를 RAG / GraphRAG / KG-QA 기준으로 비교

이제 이걸 LLM 시스템으로 옮겨 보자. 세 방식은 사실 **“질문을 받았을 때 어떤 외부 지식을 어떻게 꺼내고, 어느 수준에서 구조를 활용하느냐”**의 차이다.

### 4-1. RAG

가장 기본적인 RAG는 대체로
**질문 → 텍스트 청크 검색 → 관련 문맥을 프롬프트에 삽입 → LLM 생성**
흐름이다. 원래 RAG는 parametric memory와 non-parametric memory를 결합해 knowledge-intensive task를 다루기 위한 프레임워크로 제안되었고, LLM 시대에는 최신 외부 지식을 붙여 생성 품질을 높이는 전형적인 구조가 되었다. ([arXiv][8])

장점은 구현이 가장 쉽고, 문서 기반 QA에 바로 붙이기 좋다는 점이다. 반면 검색 단위가 보통 **텍스트 청크**라서, 엔터티 간 관계가 여러 문서에 흩어져 있거나 다단계 연결이 중요한 질문에서는 약해질 수 있다. 이 한계 때문에 그래프 구조를 도입한 GraphRAG 계열이 부상했다. ([arXiv][9])

### 4-2. GraphRAG

GraphRAG는 대체로
**질문 → 그래프 기반 인덱싱/엔터티 연결 → 노드·엣지·패스·서브그래프 검색 → 구조를 반영한 컨텍스트 구성 → LLM 생성**
흐름으로 본다. GraphRAG 서베이는 이를 **graph-based indexing, graph-guided retrieval, graph-enhanced generation**의 세 단계로 정리한다. ([arXiv][10])

핵심 차이는 검색 단위가 단순 텍스트 덩어리가 아니라 **엔터티와 관계 구조**라는 점이다. 그래서 GraphRAG는 relational information, multi-hop dependencies, cross-document structure를 다루는 데 유리하다고 평가된다. 텍스트만으로는 드러나지 않는 연결을 그래프가 명시적으로 잡아주기 때문이다. ([arXiv][10])

다만 GraphRAG는 그래프를 잘 만들어야 하고, 어떤 노드·패스·서브그래프를 꺼낼지 설계가 중요하다. 즉 **관계 구조가 중요한 질문에는 강하지만**, 그래프 구축 비용과 retrieval 설계 난도가 올라간다. ([arXiv][10])

### 4-3. KG-QA

KG-QA는 대체로
**질문 → 엔터티/관계 파악 → 질의 그래프 또는 SPARQL 같은 실행 가능한 형식 생성, 혹은 관련 서브그래프 추출 → KG 위에서 정확한 답 계산 → 필요하면 자연어로 표면화**
흐름으로 본다. KGQA는 오랫동안 KG 기반 질의응답 분야로 발전해 왔고, 최근에도 semantic parsing 기반과 subgraph retrieval/reasoning 기반 접근이 주요 축으로 다뤄진다. ([2024.eswc-conferences.org][11])

이 방식의 강점은 **정확성, 추적 가능성, 구조적 일관성**이다. 특히 도메인 KG가 잘 정제되어 있고 질문이 그 KG의 스키마와 잘 맞을 때, KG-QA는 “어떤 경로로 답이 나왔는지”를 설명하기 쉽고, SPARQL 실행 결과처럼 검사 가능한 답을 내기 좋다. ESWC 2024의 프레임워크 설명도 결국 LLM이 SPARQL 질의를 만들고, 이를 KG에서 실행한 뒤 자연어 응답으로 바꾸는 흐름을 제시한다. ([2024.eswc-conferences.org][11])

반면 약점은 질문이 KG 스키마와 멀거나, 답에 필요한 정보가 KG 밖 텍스트에 많이 있을 때다. 또 entity linking, schema linking, text-to-SPARQL이 틀리면 전체 파이프라인이 쉽게 흔들린다. ([arXiv][12])

## 5. 세 방식을 한 질문 위에 올려 보면

예를 들어 질문이
**“서울의 수도 관계를 통해 연결되는 국가는 어디이며, 그 나라의 공식 수도 표기는 무엇인가?”**
같이 관계 중심이라면 차이는 더 잘 보인다.

RAG는 관련 문서 조각을 모아 LLM이 답을 합성한다. 문서에 정답 문장이 잘 들어 있으면 강하다. 하지만 정보가 여러 문서에 흩어져 있고 관계를 명시적으로 따라가야 하면, retrieval과 synthesis가 불안정해질 수 있다. ([arXiv][8])

GraphRAG는 `Seoul → capitalOf → SouthKorea` 같은 연결 자체를 retrieval의 단위로 쓰기 쉬워서, 관계 중심 질문이나 다단계 연결 질문에서 유리하다. GraphRAG 서베이의 핵심 주장도 바로 이 relational retrieval 강점이다. ([arXiv][10])

KG-QA는 아예 “이 질문을 어떤 그래프 질의로 바꿀까”에 초점을 둔다. 따라서 도메인 KG 안에 필요한 사실이 있다면 가장 깔끔하게 답을 낼 수 있다. 대신 질문이 느슨하거나 KG 밖 배경지식이 많이 필요하면 유연성은 떨어질 수 있다. ([2024.eswc-conferences.org][11])

## 6. 언제 무엇을 쓰는가

문서가 주 자산이고, 답도 대체로 문서 근거 문장들을 잘 엮으면 되는 환경이면 **RAG**가 가장 경제적이다. 특히 구축 속도와 운영 단순성이 장점이다. ([arXiv][9])

문서는 많지만, 답이 엔터티 관계망을 따라가야 하고 여러 출처를 구조적으로 묶어야 한다면 **GraphRAG**가 더 자연스럽다. GraphRAG는 텍스트 기반 검색의 한계였던 관계 구조 손실을 줄이려는 흐름으로 이해하면 된다. ([arXiv][10])

도메인 KG가 이미 잘 정리돼 있고, 정답성·재현성·검사 가능성이 중요하다면 **KG-QA**가 가장 강하다. 특히 규정, 제품 카탈로그, 과학 지식, 엔터프라이즈 마스터데이터처럼 스키마가 분명한 경우가 그렇다. ([2024.eswc-conferences.org][11])

## 7. 가장 현실적인 결론

실무적으로는 셋이 경쟁 관계라기보다 **계층적으로 결합**되는 경우가 많다.
예를 들면 **텍스트 문서를 RAG로 검색하고**, 그 안의 엔터티·관계를 **GraphRAG 방식으로 구조화해 재검색**하고, 특정 정밀 질의는 **KG-QA/SPARQL로 실행**한 뒤, 마지막 응답만 LLM이 자연어로 정리하는 식이다. 이 결론은 GraphRAG의 단계적 파이프라인, KG-enhanced RAG 서베이, 그리고 LLM 기반 KG-QA 프레임워크들을 종합한 해석이다. ([arXiv][13])

한 줄로 정리하면 이렇다.

- **RAG**: 텍스트를 잘 찾고 잘 요약하는 구조
- **GraphRAG**: 관계 구조를 살려 찾고 요약하는 구조
- **KG-QA**: KG를 직접 질의·추론해서 답을 계산하는 구조 ([arXiv][8])

[1]: https://www.w3.org/TR/rdf11-concepts/?utm_source=chatgpt.com "RDF 1.1 Concepts and Abstract Syntax"
[2]: https://www.w3.org/TR/turtle/?utm_source=chatgpt.com "RDF 1.1 Turtle"
[3]: https://www.w3.org/TR/owl2-primer/?utm_source=chatgpt.com "OWL 2 Web Ontology Language Primer (Second Edition)"
[4]: https://www.w3.org/TR/sparql11-entailment/?utm_source=chatgpt.com "SPARQL 1.1 Entailment Regimes"
[5]: https://www.w3.org/TR/sparql11-query/?utm_source=chatgpt.com "SPARQL 1.1 Query Language"
[6]: https://www.w3.org/TR/sparql11-query/diff?utm_source=chatgpt.com "SPARQL 1.1 Query Language"
[7]: https://www.w3.org/TR/sparql-features/?utm_source=chatgpt.com "SPARQL New Features and Rationale"
[8]: https://arxiv.org/pdf/2005.11401?utm_source=chatgpt.com "Retrieval-Augmented Generation for Knowledge-Intensive ..."
[9]: https://arxiv.org/abs/2405.06211?utm_source=chatgpt.com "A Survey on RAG Meeting LLMs: Towards Retrieval-Augmented Large Language Models"
[10]: https://arxiv.org/abs/2408.08921?utm_source=chatgpt.com "Graph Retrieval-Augmented Generation: A Survey"
[11]: https://2024.eswc-conferences.org/wp-content/uploads/2024/05/77770162.pdf?utm_source=chatgpt.com "A Framework for Question Answering on Knowledge ..."
[12]: https://arxiv.org/abs/2406.14191?utm_source=chatgpt.com "Temporal Knowledge Graph Question Answering: A Survey"
[13]: https://arxiv.org/pdf/2408.08921?utm_source=chatgpt.com "Graph Retrieval-Augmented Generation: A Survey"
