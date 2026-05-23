#!/usr/bin/env python3
"""Smoke test for ntfy push notifications.

Sends one message per priority level to verify delivery end-to-end.

Usage:
    NTFY_TOPIC=my-topic uv run python scripts/smoke_ntfy.py
    NTFY_TOPIC_GPT=my-gpt-topic uv run python scripts/smoke_ntfy.py --gpt
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import httpx


def send(topic: str, title: str, message: str, *, priority: int, tags: tuple[str, ...]) -> None:
    headers: dict[str, str] = {
        "Title": title,
        "Priority": str(priority),
    }
    if tags:
        headers["Tags"] = ",".join(tags)

    try:
        resp = httpx.post(f"https://ntfy.sh/{topic}", content=message.encode(), headers=headers, timeout=10)
        resp.raise_for_status()
        print(f"  [{resp.status_code}] {title}")
    except Exception as exc:
        print(f"  [ERROR] {title}: {exc}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test for ntfy notifications")
    parser.add_argument("--gpt", action="store_true", help="Use NTFY_TOPIC_GPT instead of NTFY_TOPIC")
    args = parser.parse_args()

    env_var = "NTFY_TOPIC_GPT" if args.gpt else "NTFY_TOPIC"
    topic = os.environ.get(env_var, "")
    if not topic:
        print(f"ERROR: {env_var} no está configurado.", file=sys.stderr)
        sys.exit(1)

    print(f"Enviando smoke messages a ntfy.sh/{topic} …\n")

    messages = [
        ("Smoke - Info",    "Mensaje de prueba (prioridad normal)",  3, ("white_check_mark",)),
        ("Smoke - Warning", "Mensaje de prueba (prioridad alta)",    4, ("warning",)),
        ("Smoke - OK",      "Todo listo, ntfy funciona correctamente", 5, ("tada", "partying_face")),
    ]

    for title, body, priority, tags in messages:
        send(topic, title, body, priority=priority, tags=tags)
        time.sleep(1)

    print("\nDone. Comprueba las notificaciones en tu dispositivo.")


if __name__ == "__main__":
    main()
