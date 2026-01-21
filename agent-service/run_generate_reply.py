import argparse
import json
import os
import sys


def _bootstrap():
    service_root = os.path.dirname(__file__)
    src_path = os.path.join(service_root, "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


_bootstrap()

from x_agent_os.agents.reply_agent import ReplyAgent
from x_agent_os.database import DatabaseHandler


def main():
    parser = argparse.ArgumentParser(description="Generate reply for a conversation")
    parser.add_argument("--conversation-id", type=int, required=True)
    args = parser.parse_args()

    db = DatabaseHandler()
    agent = ReplyAgent(db)
    reply = agent.generate_reply_for_conversation(args.conversation_id)
    print(json.dumps({"reply": reply}))


if __name__ == "__main__":
    main()
