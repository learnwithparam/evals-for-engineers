"""uv run fernhill [demo|report|gate]: the finished system."""

import sys


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "help"
    arguments = sys.argv[2:]
    if command == "demo":
        from .evals.report import demo

        return demo(arguments)
    if command == "report":
        from .evals.report import report

        return report(arguments)
    if command == "gate":
        from .evals.gate import main as gate

        return gate(arguments)
    print("Use: uv run fernhill demo | report | gate --release <name>")
    return 1


if __name__ == "__main__":
    sys.exit(main())
