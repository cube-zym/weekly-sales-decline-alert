#!/usr/bin/env bash
# 拉取领星 erp_listing 分页数据（新协议 help->search->action；凭证从 config.json 读取）
set -euo pipefail

OUT_DIR="${1:-.}"
PAGES="${PAGES:-5}"
LENGTH="${LENGTH:-100}"
SIDS="${SIDS:-1}"          # 店铺ID，1=GreatStar Tools US（逗号分隔可多店铺）
CATALOG="basic-open-online-20260825-v3"
SCHEMA="erp_listing-v1"

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
  PARAMS=$(python3 -c "import json,sys;print(json.dumps({'offset':$OFF,'length':$LENGTH,'pvi_ids':'','sids':'$SIDS'}))")
  PAYLOAD=$(python3 -c "import json,sys;print(json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'action','arguments':{'toolId':'erp_listing','catalogVersion':'$CATALOG','schemaVersion':'$SCHEMA','paramsJson':sys.argv[1]}}},ensure_ascii=False))" "$PARAMS")
  curl -s -m 90 -X POST "$URL" \
    -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
    -H "X-Mcp-Key: $KEY" \
    -d "$PAYLOAD" > "$OUT_DIR/listing_p$i.json"
  SIZE=$(wc -c < "$OUT_DIR/listing_p$i.json")
  echo "page $i: $SIZE bytes"
  if [ "$SIZE" -lt 500 ]; then
    echo "警告: 第 $i 页响应过小，可能出错:" >&2
    head -c 300 "$OUT_DIR/listing_p$i.json" >&2; echo >&2
    break
  fi
done
echo "完成: 数据已保存到 $OUT_DIR/ (店铺 sids=${SIDS})"
