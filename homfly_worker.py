"""Standalone HOMFLY worker: reads a pickled (chain, tries) from stdin, writes the pickled result to stdout.
Run in a fresh interpreter because forking the multithreaded Dash process corrupts/deadlocks the child's heap."""
import os
import pickle
import sys


def main():
    chain, _tries = pickle.load(sys.stdin.buffer)
    out = os.fdopen(os.dup(1), 'wb')
    # Keep stray prints from topoly off the result channel.
    os.dup2(sys.stderr.fileno(), 1)
    import topoly as tp
    from topoly import Closure
    try:
        res = tp.homfly(chain, closure=Closure.CLOSED, run_parallel=False, chiral=True,
                       hide_trivial=False)
        # A closed chain yields a single knot name instead of a probability dict.
        if isinstance(res, str):
            res = {res: 1.0} if res else None
    except Exception:
        res = None
    pickle.dump(res, out)
    out.flush()


if __name__ == '__main__':
    main()
