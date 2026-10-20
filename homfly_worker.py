"""Standalone HOMFLY worker: reads a pickled (chain, tries) from stdin, writes the pickled result to stdout.
Run in a fresh interpreter because forking the multithreaded Dash process corrupts/deadlocks the child's heap."""
import os
import pickle
import sys


def main():
    chain, tries = pickle.load(sys.stdin.buffer)
    out = os.fdopen(os.dup(1), 'wb')
    # Keep stray prints from topoly off the result channel.
    os.dup2(sys.stderr.fileno(), 1)
    import topoly as tp
    try:
        res = tp.homfly(chain, tries=tries, run_parallel=False, chiral=True)
    except Exception:
        res = None
    pickle.dump(res, out)
    out.flush()


if __name__ == '__main__':
    main()
