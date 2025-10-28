"""Simple DNS client runner
"""
import dns.resolver
import time
import os

QUERY_LIST_FILE = os.path.join(os.path.dirname(__file__), 'queries2.txt')
RESULTS_CSV = os.path.join(os.path.dirname(__file__), 'h1_client_results.csv')


def do_resolve(name):
    """Resolve a domain name to A records and measure latency (ms).

    Returns (list_of_ips or None, elapsed_ms or None)
    """
    resolver = dns.resolver.Resolver()
    resolver.timeout = 3
    resolver.lifetime = 3
    try:
        t0 = time.perf_counter()
        ans = resolver.resolve(name, 'A')
        elapsed = (time.perf_counter() - t0) * 1000
        ips = [rr.address for rr in ans]
        return ips, elapsed
    except Exception:
        return None, None


def main():
    if not os.path.exists(QUERY_LIST_FILE):
        print(f"[ERROR] Query file not found: {QUERY_LIST_FILE}")
        return

    with open(QUERY_LIST_FILE, 'r', encoding='utf-8') as fh:
        domains = [ln.strip() for ln in fh if ln.strip()]

    total = len(domains)
    print(f"Running {total} DNS queries from {QUERY_LIST_FILE}...\n")

    succ = 0
    fail = 0
    sum_latency = 0.0

    for i, dom in enumerate(domains, start=1):
        ips, ms = do_resolve(dom)
        if ips:
            print(f"[{i}/{total}] {dom} -> {', '.join(ips)} ({ms:.1f} ms)")
            succ += 1
            sum_latency += ms
        else:
            print(f"[{i}/{total}] {dom} -> FAIL")
            fail += 1
        time.sleep(0.3)

    avg = sum_latency / succ if succ else 0.0

    print('\n=== Summary ===')
    print(f"Total queries: {total}")
    print(f"Successful: {succ}")
    print(f"Failed: {fail}")
    print(f"Average latency: {avg:.2f} ms")

    with open(RESULTS_CSV, 'a', encoding='utf-8') as out:
        out.write(f"H1,{total},{succ},{fail},{avg:.2f}\n")

    print(f"\nResults saved to {RESULTS_CSV}")


if __name__ == '__main__':
    main()
