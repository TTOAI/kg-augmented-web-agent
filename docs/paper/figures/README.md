# Figures

Mermaid source (.mmd) + rendered PNG. PNG는 git에 커밋해 reviewer/재현자가 렌더링 툴
없이도 열람 가능.

## Files

- `skg_architecture.mmd` — Figure 1: SiteKG-augmented Web Agent Architecture
- `skg_architecture.png` — rendered (수동 렌더)
- `pipeline.mmd` — Figure 2: 2-stage Automated KG Construction Pipeline
- `pipeline.png` — rendered (수동 렌더)

## Rendering

### Option A — mermaid-cli (local)

```bash
npm install -g @mermaid-js/mermaid-cli
mmdc -i skg_architecture.mmd -o skg_architecture.png -t neutral -b transparent
mmdc -i pipeline.mmd -o pipeline.png -t neutral -b transparent
```

### Option B — mermaid.live (online)

1. https://mermaid.live 접속
2. `.mmd` 내용 붙여넣기
3. "Actions" → "PNG" 다운로드

### Option C — draw.io / diagrams.net

`.mmd` → Edit → Insert → Advanced → Mermaid 후 붙여넣기 → Export as PNG.

## 최종 논문 투고용

학회별 포맷 (IEEE / ACM / Korean 학회)에 따라 TikZ 또는 PDF vector figure로 재생성
가능. 본 `.mmd`는 **소스 of truth**로 유지.
