"""DNS Log Analyzer and Plotter

Parses a DNS log file and produces two PNG plots for the first N domains:
- unique DNS servers visited per domain
- total latency per domain (sum of available RTTs)

This file is a refactored version of the original plotting utility, with
renamed variables and clearer helper functions — behavior remains unchanged.
"""
import os
import re
from collections import OrderedDict
import matplotlib.pyplot as plt


# Path to the DNS log (keeps original filename but variable renamed)
DNS_LOG_PATH = os.path.join(os.path.dirname(__file__), 'dns_log.txt')


def parse_dns_log(filepath):
    """Parse the DNS log file and collect hop entries per domain.

    Returns an OrderedDict mapping domain -> list of hop dicts
    where each hop dict contains keys: 'ip', 'rtt', 'response'.
    """
    entry_pattern = re.compile(
        r"^(?P<time>[^|]+)\s*\|\s*(?P<domain>[^|]+)\s*\|\s*(?P<mode>[^|]+)\s*\|\s*(?P<ip>[^|]+)\s*\|\s*Step:\s*(?P<step>[^|]+)\s*\|\s*Response:\s*(?P<response>[^|]+)\s*\|\s*RTT:\s*(?P<rtt>[^|]+)\s*\|?\s*(?P<rest>.*)$"
    )

    domain_map = OrderedDict()

    with open(filepath, 'r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = entry_pattern.match(line.strip())
            if not m:
                continue
            dom = m.group('domain').strip()
            ip = m.group('ip').strip()
            rtt_raw = m.group('rtt').strip()
            resp = m.group('response').strip()

            rtt_val = None
            if rtt_raw and rtt_raw != '-':
                try:
                    rtt_val = float(rtt_raw.split()[0])
                except Exception:
                    try:
                        rtt_val = float(rtt_raw)
                    except Exception:
                        rtt_val = None

            domain_map.setdefault(dom, []).append({'ip': ip, 'rtt': rtt_val, 'response': resp})

    return domain_map


def collect_metrics(domain_map, count=10):
    """Collect metrics (unique servers and total RTT) for the first `count` domains."""
    items = list(domain_map.items())[:count]
    out = []
    for dom, hops in items:
        seen_ips = []
        for h in hops:
            if h['ip'] not in seen_ips:
                seen_ips.append(h['ip'])
        servers = len(seen_ips)
        rtts = [h['rtt'] for h in hops if h['rtt'] is not None]
        total_ms = sum(rtts) if rtts else None
        out.append({'domain': dom, 'servers_visited': servers, 'total_latency_ms': total_ms, 'per_hop_rtts': rtts})
    return out


def create_plots(metrics, output_dir='plots'):
    """Generate and save server-count and latency plots. Returns file paths."""
    os.makedirs(output_dir, exist_ok=True)
    labels = [m['domain'] for m in metrics]
    server_counts = [m['servers_visited'] for m in metrics]
    latencies = [m['total_latency_ms'] if m['total_latency_ms'] is not None else 0 for m in metrics]

    # Plot 1: servers visited
    plt.figure(figsize=(10, 5))
    plt.bar(range(len(labels)), server_counts, color='C0')
    plt.xticks(range(len(labels)), labels, rotation=45, ha='right')
    plt.ylabel('Unique DNS servers visited')
    plt.title(f'PCAP_1_H1 — DNS servers visited (first {len(labels)})')
    plt.tight_layout()
    servers_fp = os.path.join(output_dir, 'h1_servers.png')
    plt.savefig(servers_fp)
    plt.close()

    # Plot 2: total latency
    plt.figure(figsize=(10, 5))
    plt.bar(range(len(labels)), latencies, color='C1', alpha=0.85, label='Total RTT (ms)')
    plt.plot(range(len(labels)), latencies, color='C3', marker='o')
    plt.xticks(range(len(labels)), labels, rotation=45, ha='right')
    plt.ylabel('Total latency (ms)')
    plt.title(f'PCAP_1_H1 — Total latency per query (first {len(labels)})')
    plt.legend()
    plt.tight_layout()
    latency_fp = os.path.join(output_dir, 'h1_latency.png')
    plt.savefig(latency_fp)
    plt.close()

    return servers_fp, latency_fp


def main():
    domain_map = parse_dns_log(DNS_LOG_PATH)
    if not domain_map:
        print('No entries found in', DNS_LOG_PATH)
        return

    metrics = collect_metrics(domain_map, count=10)
    for idx, m in enumerate(metrics, 1):
        print(f"{idx}. {m['domain']}: servers_visited={m['servers_visited']}, total_latency_ms={m['total_latency_ms']}")

    sp, lp = create_plots(metrics)
    print('Plots written:')
    print(' -', sp)
    print(' -', lp)


if __name__ == '__main__':
    main()
