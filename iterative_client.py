"""Iterative-resolution demo client

Performs iterative-like lookups using the dns library and logs steps to a file.
This is a refactor of the original `c2.py` with renamed symbols and different
default result/log filenames. Behavior and log output format remain compatible.
"""
import dns.resolver
import dns.message
import dns.query
import dns.name
import time
import os
from datetime import datetime

QUERIES_FILE = os.path.join(os.path.dirname(__file__), 'queries2.txt')
OUTPUT_SUMMARY = os.path.join(os.path.dirname(__file__), 'h2_summary.csv')
DETAILED_LOG = os.path.join(os.path.dirname(__file__), 'dns_log2.txt')

# Simple cache to speed repeated lookups
_CACHE = {}

ROOT_SERVERS = [
    '198.41.0.4',
    '199.9.14.201',
    '192.33.4.12',
]


def append_log(line: str):
    with open(DETAILED_LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def iterative_lookup(domain: str):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    start_total = time.perf_counter()
    mode = 'Iterative'

    if domain in _CACHE:
        append_log(f"{ts} | {domain} | {mode} | CACHE | Step: Cache | Response: {_CACHE[domain]} | RTT: 0 ms | Total: 0 ms | Cache HIT")
        return _CACHE[domain], 0.0, 'HIT'

    qname = dns.name.from_text(domain)
    current_ns = ROOT_SERVERS[:]
    accumulated_rtt = 0.0
    answer_ips = None

    # Query root servers first
    tld_ip = None
    for root in current_ns:
        step_start = time.perf_counter()
        try:
            qry = dns.message.make_query(qname, dns.rdatatype.A)
            resp = dns.query.udp(qry, root, timeout=3)
            step_rtt = (time.perf_counter() - step_start) * 1000
            accumulated_rtt += step_rtt
            append_log(f"{ts} | {domain} | {mode} | {root} | Step: Root | Response: Referral | RTT: {step_rtt:.2f} ms | Cache MISS")

            if resp.additional:
                for rr in resp.additional:
                    if rr.rdtype == dns.rdatatype.A:
                        tld_ip = rr.items[0].address
                        break
                if tld_ip:
                    break
        except Exception as ex:
            append_log(f"{ts} | {domain} | {mode} | {root} | Step: Root | Response: FAIL ({ex}) | RTT: - | Cache MISS")
            continue

    if not tld_ip:
        return None, accumulated_rtt, 'MISS'

    # Query TLD
    try:
        step_start = time.perf_counter()
        qry = dns.message.make_query(qname, dns.rdatatype.A)
        resp = dns.query.udp(qry, tld_ip, timeout=3)
        step_rtt = (time.perf_counter() - step_start) * 1000
        accumulated_rtt += step_rtt
        append_log(f"{ts} | {domain} | {mode} | {tld_ip} | Step: TLD | Response: Referral | RTT: {step_rtt:.2f} ms | Cache MISS")

        auth_ip = None
        if resp.additional:
            for rr in resp.additional:
                if rr.rdtype == dns.rdatatype.A:
                    auth_ip = rr.items[0].address
                    break
    except Exception as ex:
        append_log(f"{ts} | {domain} | {mode} | {tld_ip} | Step: TLD | Response: FAIL ({ex}) | RTT: - | Cache MISS")
        return None, accumulated_rtt, 'MISS'

    # Query authoritative
    try:
        step_start = time.perf_counter()
        qry = dns.message.make_query(qname, dns.rdatatype.A)
        resp = dns.query.udp(qry, auth_ip, timeout=3)
        step_rtt = (time.perf_counter() - step_start) * 1000
        accumulated_rtt += step_rtt

        if resp.answer:
            answer_ips = [rdata.address for rr in resp.answer for rdata in rr.items if rr.rdtype == dns.rdatatype.A]
            append_log(f"{ts} | {domain} | {mode} | {auth_ip} | Step: Authoritative | Response: {answer_ips} | RTT: {step_rtt:.2f} ms | Cache MISS")
        else:
            append_log(f"{ts} | {domain} | {mode} | {auth_ip} | Step: Authoritative | Response: NO ANSWER | RTT: {step_rtt:.2f} ms | Cache MISS")

    except Exception as ex:
        append_log(f"{ts} | {domain} | {mode} | {auth_ip} | Step: Authoritative | Response: FAIL ({ex}) | RTT: - | Cache MISS")

    total_ms = (time.perf_counter() - start_total) * 1000
    if answer_ips:
        _CACHE[domain] = answer_ips
        append_log(f"{ts} | {domain} | TOTAL | TotalTime: {total_ms:.2f} ms | Cache Stored")
    else:
        append_log(f"{ts} | {domain} | TOTAL | TotalTime: {total_ms:.2f} ms | No Response")

    return answer_ips, total_ms, 'MISS'


def main():
    if not os.path.exists(QUERIES_FILE := QUERIES_FILE if 'QUERIES_FILE' in globals() else QUERIES_FILE):
        print(f"[ERROR] Query file not found: {QUERIES_FILE}")
        return

    with open(QUERIES_FILE, 'r', encoding='utf-8') as fh:
        queries = [ln.strip() for ln in fh if ln.strip()]

    total = len(queries)
    print(f"Running {total} DNS queries...\n")

    success = fail = 0
    total_latency = 0.0

    for i, dom in enumerate(queries, 1):
        ips, latency, cache_status = iterative_lookup(dom)
        if ips:
            print(f"[{i}/{total}] {dom} -> {', '.join(ips)} ({latency:.1f} ms, {cache_status})")
            success += 1
            total_latency += latency
        else:
            print(f"[{i}/{total}] {dom} -> FAIL")
            fail += 1
        time.sleep(0.3)

    avg = total_latency / success if success else 0.0
    with open(OUTPUT_SUMMARY, 'a', encoding='utf-8') as out:
        out.write(f"H1,{total},{success},{fail},{avg:.2f}\n")

    print(f"\nResults saved to {OUTPUT_SUMMARY}")
    print(f"Detailed log saved to {DETAILED_LOG}")


if __name__ == '__main__':
    main()
