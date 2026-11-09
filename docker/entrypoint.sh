#!/bin/sh
set -e

mkdir -p /data/uploads /data/traces

if [ "$(id -u)" = "0" ]; then
  chown -R forensics:forensics /data
fi

run_as_forensics() {
  if [ "$(id -u)" = "0" ]; then
    exec gosu forensics "$@"
  else
    exec "$@"
  fi
}

if [ -n "${DATABASE_URL:-}" ] || [ -n "${FORENSICS_DATABASE_URL:-}" ]; then
  if [ "$(id -u)" = "0" ]; then
    gosu forensics alembic upgrade head
  else
    alembic upgrade head
  fi
fi

run_as_forensics forensics serve
