#!/usr/bin/env bash
# 拉取领星 erp_listing 分页数据（元工具协议：先 search 取最新版本，再 action 分页执行；凭证从 config.json 读取）
set -euo pipefail

OUT_DIR="${1:-.}"
PAGES="${PAGES:-5}"
LENGTH="${LENGTH:-100}"
SIDS="${SIDS:-1}"          # 店铺ID，1=GreatStar Tools US（逗号分隔可多店铺）

CFG="$HOME/.zcode/cli/config.json"
if [ ! -f "$CFG" ]; then
  echo "错误: 未找到 $CFG（领星 MCP 未配置）" >&2
  exit 1
fi

URL=$(python3 -c "import json;print(json.load(open('$CFG'))['mcp']['servers']['LingXing-MCP']['url'])")
KEY=$(python3 -c "import json;print(json.load(open('$CFG'))['mcp']['servers']['LingXing-MCP']['headers']['X-Mcp-Key'])")

# Step 1: search 获取 erp_listing 最新版本（元工具协议要求每次执行前获取）
SEARCH_PAYLOAD='{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search","arguments":{"toolId":"erp_listing"}}}'
curl -s -m 30 -X POST "$URL" \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -H "X-Mcp-Key: $KEY" -d "$SEARCH_PAYLOAD" > /tmp/lx_search_resp.json

read -r CATALOG SCHEMA VERSION_ID <<< $(python3 /dev/stdin << 'PYEOF'
import json
raw = open('/tmp/lx_search_resp.json').read().strip()
resp = json.loads(raw) if raw.startswith('{') else json.loads([l[5:] for l in raw.splitlines() if l.startswith('data: ')][-1])
text = resp['result']['content'][0]['text']
obj = json.loads(text)
d = obj.get('data', obj)
print(d.get('catalogVersion', ''), d.get('schemaVersion', ''), d.get('toolVersionId', ''))
PYEOF
)
if [ -z "$CATALOG" ]; then
  echo "错误: search 未返回版本信息" >&2
  echo "$SEARCH_RESP" | head -c 400 >&2
  exit 1
fi
echo "版本: catalog=$CATALOG schema=$SCHEMA versionId=$VERSION_ID"

mkdir -p "$OUT_DIR"
for ((i=0; i<PAGES; i++)); do
  OFF=$((i * LENGTH))
  PAYLOAD=$(python3 -c "import json,sys;print(json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'action','arguments':{'toolId':'erp_listing','catalogVersion':sys.argv[1],'schemaVersion':sys.argv[2],'toolVersionId':int(sys.argv[3]) if sys.argv[3] else None,'params':{'offset':$OFF,'length':$LENGTH,'pvi_ids':'','sids':sys.argv[4]}}}},ensure_ascii=False))" "$CATALOG" "$SCHEMA" "$VERSION_ID" "$SIDS")
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
