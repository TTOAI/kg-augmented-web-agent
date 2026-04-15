이 둘은 따로가 아니라 **한 흐름**으로 이해하면 훨씬 잘 잡힙니다.
**RDF/OWL/SPARQL 관점에서 본 KG의 내부 구조**는 결국 “사실을 어떻게 저장하고, 의미를 어떻게 붙이고, 그 위에서 어떻게 질의·추론하느냐”의 문제이고, **LLM 시대에 KG가 다시 중요해진 이유**도 바로 이 구조가 LLM의 약점을 보완해주기 때문입니다. ([W3C][1])

## 1. RDF/OWL/SPARQL 기준으로 보면 KG는 어떻게 생겼나

가장 밑바닥에는 **RDF**가 있습니다. RDF는 정보를 **주어–술어–목적어(subject–predicate–object)** 형태의 트리플로 표현하는 데이터 모델이고, RDF 그래프는 이런 트리플의 집합입니다. 트리플의 요소는 IRI, blank node, datatype literal이 될 수 있습니다. 또 RDF는 한 개의 그래프만 다루는 데서 끝나지 않고, **default graph + zero or more named graphs**로 이루어진 **RDF dataset** 개념도 제공합니다. 즉, KG의 “사실(facts)”은 보통 RDF 그래프 또는 RDF dataset 형태로 놓입니다. ([W3C][1])

그다음 층은 보통 **RDFS(RDF Schema)**입니다. 엄밀히 말해 질문에는 RDF/OWL/SPARQL만 나왔지만, 실제 KG 내부 구조를 설명할 때는 RDFS를 빼면 중간 다리가 사라집니다. RDFS는 RDF 데이터에 대해 **class, property, subclass, subproperty, domain, range** 같은 기본 데이터 모델링 어휘를 제공합니다. 중요한 점은, RDFS의 domain/range는 SQL 스키마처럼 “입력을 강하게 막는 제약”이라기보다 **의미를 부여하고 추론에 활용되는 기술적 장치**라는 점입니다. W3C 문서도 RDFS가 이런 정보를 기술하는 메커니즘을 제공하지만, 애플리케이션이 그것을 어떻게 사용할지는 정하지 않는다고 설명합니다. ([W3C][2])

그 위에 **OWL**이 있습니다. OWL은 W3C가 정의한 온톨로지 언어로, **classes, properties, individuals, data values**를 더 풍부하고 형식적으로 표현하게 해 줍니다. 쉽게 말하면 RDF/RDFS가 “그래프 모양의 사실 + 기본 분류”라면, OWL은 그 위에 **더 강한 의미론과 추론 가능성**을 올리는 층입니다. W3C는 OWL 2 온톨로지를 추상 구조로도 볼 수 있고, 동시에 **RDF graph로도 볼 수 있다**고 설명합니다. 또 OWL 2에는 **EL, QL, RL** 같은 프로파일이 있어서, 표현력과 계산 비용 사이의 균형을 상황에 맞게 선택할 수 있습니다. ([W3C][3])

마지막으로 **SPARQL**이 있습니다. SPARQL은 RDF 그래프를 **질의하고 조작하는** 표준 언어와 프로토콜 집합입니다. 단순 SELECT만 있는 것이 아니라, SPARQL 1.1은 **Update, Federated Query, Entailment Regimes**까지 포함합니다. 질의 표현력도 꽤 높아서 **OPTIONAL**, **UNION**, **FILTER**, **property paths** 등을 통해 부분 정보 질의, 대안 경로 탐색, 다단계 관계 탐색을 할 수 있습니다. 즉 RDF/OWL이 “지식을 어떻게 표현할지”를 담당한다면, SPARQL은 “그 지식을 어떻게 꺼내 쓰고 연결할지”를 담당합니다. ([W3C][4])

정리하면, KG를 이 관점에서 볼 때 내부 구조는 대체로 이렇게 이해하면 됩니다.

- **RDF**: 사실 저장층
- **RDFS**: 기본 스키마/어휘층
- **OWL**: 온톨로지·의미론·추론층
- **SPARQL**: 질의·조작·연결층

이 네 층이 합쳐져야 “그냥 연결된 데이터”가 아니라 **의미 있는 지식 그래프**가 됩니다. 이 구조적 구분은 KG 연구 서베이에서도 schema, identity, context, query language의 역할을 구분해 설명하는 방식과 잘 맞습니다. ([arXiv][5])

## 2. 아주 작은 예로 보면

예를 들어 이런 식입니다.

```turtle
ex:Seoul ex:capitalOf ex:SouthKorea .
ex:capitalOf rdfs:domain ex:City .
ex:capitalOf rdfs:range ex:Country .
```

이 경우 RDF 수준에서는 단순히 “서울이 한국의 수도다”라는 **사실 트리플**이 있을 뿐입니다. 하지만 RDFS를 함께 쓰면 `capitalOf`의 domain과 range 때문에 `ex:Seoul rdf:type ex:City`, `ex:SouthKorea rdf:type ex:Country` 같은 해석이 가능해집니다. 여기에 OWL을 얹으면 더 복잡한 의미 관계와 추론을 다룰 수 있고, SPARQL로는 이런 엔터티·관계·경로를 질의할 수 있습니다. 즉 KG는 단순한 저장이 아니라 **표현 + 의미 + 질의**가 결합된 구조입니다. ([W3C][2])

또 RDF dataset과 named graph를 쓰면 출처를 분리해서 보관할 수 있습니다. W3C는 named graph의 한 용도로 여러 RDF source의 snapshot을 따로 유지하는 경우를 들고 있습니다. 그래서 실무 KG에서는 named graph가 **출처 관리, 문맥 구분, provenance 처리**에 자주 연결됩니다. 이 마지막 연결은 표준 문서와 KG 서베이를 종합한 해석입니다. ([W3C][1])

## 3. 그럼 왜 LLM 시대에 KG가 다시 중요해졌나

핵심은 **LLM의 지식은 주로 파라메트릭(parametric)**이고, KG의 지식은 **명시적(explicit)**이라는 점입니다. Pan et al.은 LLM의 등장 이후 오히려 **explicit knowledge와 parametric knowledge를 함께 보는 hybrid representation**에 대한 관심이 다시 커졌다고 설명합니다. 즉 LLM이 모든 지식을 “모델 내부 가중치”로만 들고 있는 방식에는 한계가 있고, KG처럼 **밖에 명시적으로 꺼내 놓은 지식 구조**가 다시 중요해진 것입니다. ([arXiv][6])

첫째 이유는 **업데이트 가능성**입니다. LLM 내부 지식은 학습 시점 이후 쉽게 갱신되지 않지만, KG는 새 엔터티·관계·사실을 추가하거나 수정하기가 상대적으로 쉽습니다. 특히 기업 환경에서는 제품, 정책, 조직, 규정, 고객 데이터가 계속 바뀌므로, 바깥의 구조화된 지식원 없이 LLM만으로 최신성을 유지하기 어렵습니다. GraphRAG 서베이도 동적이고 적응적인 그래프 업데이트가 중요한 과제라고 지적합니다. ([arXiv][6])

둘째 이유는 **환각(hallucination) 완화와 근거 제시**입니다. NAACL 2024 서베이는 현대 LLM이 지식 공백 때문에 hallucination을 일으키기 쉽고, 이를 줄이기 위해 외부 지식을 주입하는 여러 방법 가운데 **KG 기반 증강이 유망한 결과를 보여 왔다**고 정리합니다. 또한 이 서베이는 KG가 LLM의 hallucination 완화와 reasoning accuracy 향상에 기여할 수 있다고 설명합니다. 다만 표현을 조심하면, KG는 hallucination을 “없애는 마법”이 아니라 **줄이고 통제하기 위한 유력한 외부 지식 장치**입니다.

셋째 이유는 **관계 중심 질의와 다단계 추론**입니다. 일반 텍스트 RAG는 관련 문서를 찾아 붙여 주는 데 강하지만, “A가 B에 어떤 영향을 주었고, 그 관계가 C와 어떻게 이어지나?”처럼 **관계 자체가 핵심**인 질문에서는 한계가 있습니다. GraphRAG 서베이는 그래프 기반 검색이 텍스트 간의 상호연결을 활용해 **relational information**을 더 정확하고 포괄적으로 가져올 수 있다고 설명합니다. 또 일반 텍스트 RAG가 긴 문장 속 관계를 놓치기 쉬운 반면, GraphRAG는 **explicit entity and relationship representations**를 사용해 더 정밀한 structured retrieval을 가능하게 한다고 정리합니다. ([arXiv][7])

넷째 이유는 **컨텍스트 압축과 구조적 요약**입니다. 그래프는 문장을 길게 늘어놓지 않고도 “누가 누구와 어떤 관계인가”를 압축해서 표현합니다. GraphRAG 서베이는 그래프 데이터, 특히 KG가 텍스트를 **abstraction and summarization**한 형태를 제공하여 입력 길이를 줄이고 verbosity 문제를 완화할 수 있다고 설명합니다. 그래서 긴 문서를 통째로 LLM에 넣는 대신, **관련 subgraph, path, triplet**만 꺼내서 주는 방식이 점점 중요해지고 있습니다. ([arXiv][7])

다섯째 이유는 **통제 가능성과 검사 가능성**입니다. KG는 엔터티, 관계, 타입, 출처가 비교적 명시적으로 드러나 있기 때문에, 잘못된 답이 나왔을 때 “어느 엔터티 연결이 틀렸는지”, “어느 관계가 빠졌는지”, “출처 그래프가 오래됐는지”를 추적하기가 LLM 내부 파라미터보다 훨씬 쉽습니다. Agrawal et al.도 KG를 LLM의 inference, learning, validation 단계에 걸쳐 결합하는 흐름을 정리하면서, 이런 통합이 더 **reliable and trustworthy**한 시스템으로 가는 방향이라고 봅니다.

## 4. 하지만 KG가 있다고 다 해결되는 것은 아니다

여기서 중요한 현실적 한계도 있습니다. KG를 LLM에 붙이면 좋다는 말은 맞지만, 효과는 **그래프 품질**, **엔터티 링크 정확도**, **검색 단위(노드/트리플/패스/서브그래프)**, **그래프를 LLM 입력 형식으로 번역하는 방식**에 크게 좌우됩니다. GraphRAG 서베이는 그래프를 LLM이 이해할 수 있는 형식으로 바꾸는 일 자체가 과제이고, 대규모 KG에서 적절한 엔터티를 효율적으로 검색하는 것도 중요한 실무 난제라고 지적합니다. Agrawal et al. 역시 KG-증강 LLM 기법들에 여전히 상당한 도전 과제가 남아 있다고 정리합니다.

그래서 현재 가장 균형 잡힌 결론은 이렇습니다.
**LLM이 KG를 대체한 것이 아니라, 오히려 LLM 때문에 KG의 역할이 더 선명해졌다**고 보는 편이 정확합니다. LLM은 언어 이해·생성에 강하고, KG는 **명시적 지식, 관계 구조, 추론 가능성, 갱신성, 검증성**에 강합니다. 그래서 오늘날의 방향은 “LLM vs KG”가 아니라 **LLM + KG의 하이브리드 아키텍처**로 이동하고 있다고 보는 것이 학술적으로 가장 타당합니다. ([arXiv][6])

[1]: https://www.w3.org/TR/rdf11-concepts/ "RDF 1.1 Concepts and Abstract Syntax"
[2]: https://www.w3.org/TR/rdf-schema/ "RDF Schema 1.1"
[3]: https://www.w3.org/TR/owl2-overview/ "OWL 2 Web Ontology Language Document Overview (Second Edition)"
[4]: https://www.w3.org/TR/sparql11-overview/ "SPARQL 1.1 Overview"
[5]: https://arxiv.org/abs/2003.02320 "[2003.02320] Knowledge Graphs"
[6]: https://arxiv.org/abs/2308.06374 "[2308.06374] Large Language Models and Knowledge Graphs: Opportunities and Challenges"
[7]: https://arxiv.org/pdf/2408.08921 "Graph Retrieval-Augmented Generation: A Survey"
