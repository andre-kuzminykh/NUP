#!/usr/bin/env bash
# Минимальный деплой на VM, где уже крутится твой dataist_media-контейнер.
# Поднимает наш стек рядом, своими портами (см. docker-compose.yml).
#
# Использование на твоей машине:
#   gcloud compute scp --recurse . human-1:~/nup \
#       --project=i-crossbar-433120-v3 --zone=europe-west1-b --tunnel-through-iap
#   gcloud compute ssh human-1 --project=i-crossbar-433120-v3 \
#       --zone=europe-west1-b --tunnel-through-iap \
#       --command="cd ~/nup && bash deploy.sh"

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# 1. .env-файлы — если ещё нет, копируем из примеров.
[ -f pipeline/.env ] || cp pipeline/.env.example pipeline/.env
[ -f bot/.env ]      || cp bot/example.env       bot/.env

echo
echo "=== Проверь, что обе .env заполнены: ==="
echo "  pipeline/.env: TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, TELEGRAM_CHANNEL_USERNAME, OPERATOR_CHAT_ID"
echo "  bot/.env:      BOT_TOKEN, BACKEND_URL=http://api:8010"
echo

# 2. Сборка и старт.
docker compose build
docker compose up -d

# 3. Покажем статус.
docker compose ps
echo
echo "API:        http://localhost:8010/docs"
echo "MinIO UI:   http://localhost:9021  (creds: nup / nupnupnup)"
echo "Postgres:   localhost:5440 (nup / nup)"
echo
echo "Логи:  docker compose logs -f news-worker bot api"
echo "Один прогон новостей вручную (вместо ожидания 30 мин):"
echo "  docker compose exec news-worker python -m nup_pipeline.cli.tick_once"
