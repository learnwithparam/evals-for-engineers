"""uv run fernhill [demo|report|gate]: the finished system."""
import sys


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    args = sys.argv[2:]
    if cmd == "demo":
        from .evals.report import demo
        return demo(args)
    if cmd == "report":
        from .evals.report import report
        return report(args)
    if cmd == "gate":
        from .evals.gate import main as gate
        return gate(args)
    print("Use: uv run fernhill demo | report | gate --release <name>")
    return 1


if __name__ == "__main__":
    sys.exit(main())
