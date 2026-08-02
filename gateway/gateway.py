"""Personal agent gateway.

Usage:
    python gateway.py --telegram-token <BOT_TOKEN> \
        --cloud https://api.openai.com/v1 --cloud-key sk-... [--cloud-model gpt-4o-mini] \
        [--local http://127.0.0.1:8080 --local-key sk-androidllm-...]

No cloud provider configured -> local androidllm only (offline-first).
Ctrl-C stops cleanly.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from providers import AndroidLLM, OpenAIProvider, ProviderError  # noqa: E402
from router import Router  # noqa: E402
from telegram import Telegram  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gateway", description=__doc__)
    ap.add_argument("--telegram-token", default=os.environ.get("TELEGRAM_BOT_TOKEN"))
    ap.add_argument("--cloud", default=os.environ.get("CLOUD_BASE_URL"))
    ap.add_argument("--cloud-key", default=os.environ.get("CLOUD_API_KEY"))
    ap.add_argument("--cloud-model", default=os.environ.get("CLOUD_MODEL", "gpt-4o-mini"))
    ap.add_argument("--local", default=os.environ.get("ANDROIDLLM_URL"))
    ap.add_argument("--local-key", default=os.environ.get("ANDROIDLLM_KEY"))
    args = ap.parse_args(argv)

    if not args.telegram_token:
        ap.error("--telegram-token is required")

    providers = []
    if args.cloud:
        providers.append(OpenAIProvider(args.cloud, args.cloud_key, args.cloud_model))
    if args.local:
        providers.append(AndroidLLM(args.local, args.local_key))
    if not providers:
        ap.error("configure at least one provider: --cloud or --local")

    router = Router(providers)
    bot = Telegram(args.telegram_token)
    print(f"gateway up: {[p.name for p in providers]}")
    while True:
        try:
            for update in bot.get_updates():
                text = bot.text_of(update)
                chat = bot.chat_id_of(update)
                if not text or chat is None:
                    continue
                print(f"< {bot.name_of(update)}: {text[:80]}")
                try:
                    name, resp = router.route(
                        [{"role": "user", "content": text}], max_tokens=512)
                    reply = providers_text(providers, resp, name)
                except ProviderError as e:
                    reply = f"⚠️ {e}"
                print(f"> [{name if 'name' in dir() else '?'}] {reply[:80]}")
                bot.send(chat, reply)
        except KeyboardInterrupt:
            print("\ngateway stopped")
            return 0
        except Exception as e:
            print(f"! {e}")


def providers_text(providers, resp, name):
    for p in providers:
        if p.name == name:
            return p.text_from(resp)
    return str(resp)


if __name__ == "__main__":
    main()
