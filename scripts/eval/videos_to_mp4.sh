#!/usr/bin/env bash
# Batch-convert Playwright .webm recordings to QuickTime-friendly .mp4.
#
# Playwright는 .webm(VP8/9)로만 녹화 → macOS QuickTime/미리보기 미지원.
# 각 video/*.webm 옆에 같은 이름 .mp4 생성 (libx264 + yuv420p = QT 호환).
# 이미 최신 .mp4가 있으면 skip. 측정 산출물(webm)은 보존(변환만 추가).
#
# Usage:
#   bash scripts/eval/videos_to_mp4.sh [ROOT]      # ROOT 기본 output/m2
set -u
ROOT="${1:-output/m2}"

command -v ffmpeg >/dev/null 2>&1 || { echo "[err] ffmpeg 없음 (brew install ffmpeg)"; exit 1; }
[ -d "$ROOT" ] || { echo "[err] ROOT 없음: $ROOT"; exit 1; }

n_done=0 n_skip=0 n_fail=0
while IFS= read -r webm; do
    mp4="${webm%.webm}.mp4"
    if [ -f "$mp4" ] && [ "$mp4" -nt "$webm" ]; then
        n_skip=$((n_skip + 1)); continue
    fi
    if ffmpeg -y -i "$webm" -c:v libx264 -pix_fmt yuv420p "$mp4" >/dev/null 2>&1; then
        n_done=$((n_done + 1)); echo "[ok] $mp4"
    else
        n_fail=$((n_fail + 1)); echo "[fail] $webm"
    fi
done < <(find "$ROOT" -type f -name '*.webm' | sort)

echo "----"
echo "변환 $n_done · skip $n_skip · 실패 $n_fail  (ROOT=$ROOT)"
