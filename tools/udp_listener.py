"""Print the UDP messages Lab Collector sends. Run it on the receiving computer.

    python udp_listener.py              # listen on port 5005, all network cards
    python udp_listener.py --port 6000

Needs only Python, not the app. On Windows, allow Python through the firewall
when asked, or incoming messages from other computers will be blocked.
Stop with Ctrl+C.
"""

import argparse
import json
import socket
from datetime import datetime


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=5005)
    parser.add_argument("--bind", default="0.0.0.0", help="address to listen on (default: all)")
    args = parser.parse_args()

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((args.bind, args.port))
        sock.settimeout(1.0)  # wake up every second so Ctrl+C works on Windows
        print(f"Listening for UDP messages on {args.bind}:{args.port} (Ctrl+C to stop)")
        try:
            while True:
                try:
                    data, (sender, _) = sock.recvfrom(65535)
                except TimeoutError:
                    continue
                print(f"\n[{datetime.now():%H:%M:%S}] from {sender}:")
                try:
                    print(
                        json.dumps(json.loads(data.decode("utf-8")), indent=2, ensure_ascii=False)
                    )
                except (UnicodeDecodeError, json.JSONDecodeError):
                    print(data)
        except KeyboardInterrupt:
            print("Stopped.")


if __name__ == "__main__":
    main()
