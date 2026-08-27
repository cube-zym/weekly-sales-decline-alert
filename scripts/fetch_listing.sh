#!/usr/bin/env bash
# 拉取领星 erp_listing 分页数据（凭证从 ~/.zcode/cli/config.json 读取，不硬编码）
set -euo pipefail

OUT_DIR="${1:-.}"
PAGES="${PAGES:-5}"
LENGTH="${LENGTH:-100}"

CFG="$HOME/.zcode/cli/config.json"
if [ ! -f "$CFG" ]; then
  echo "错误: 未找到 $CFG（领星 MCP 未配置）" >&2
  exit 1
fi

URL=$(python3 -c "import json;print(json.load(open('$CFG'))['mcp']['servers']['LingXing-MCP']['url'])")
KEY=$(python3 -c "import json;print(json.load(open('$CFG'))['mcp']['servers']['LingXing-MCP']['headers']['X-Mcp-Key'])")

mkdir -p "$OUT_DIR"
for ((i=0; i<PAGES; i++)); do
  OFF=$((i * LENGTH))
  curl -s -m 60 -X POST "$URL" \
    -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
    -H "X-Mcp-Key: $KEY" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"erp_listing\",\"arguments\":{\"offset\":$OFF,\"length\":$LENGTH,\"pvi_ids\":\"\"}}}" \
    > "$OUT_DIR/listing_p$i.json"
  echo "page $i: $(wc -c < "$OUT_DIR/listing_p$i.json") bytes"
done
echo "完成: $PAGES 页已保存到 $OUT_DIR/"
