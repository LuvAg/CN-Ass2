import re
from collections import defaultdict, OrderedDict
import matplotlib.pyplot as plt
import os

LOG_PATH = os.path.join(os.path.dirname(__file__), 'dns_log.txt')

def parse_log(path):
    # Parse lines like: timestamp | domain | Iterative | ip | Step: Root | Response: Referral | RTT: 189.14 ms | Cache MISS
    entry_re = re.compile(r"^(?P<time>[^|]+)\s*\|\s*(?P<domain>[^|]+)\s*\|\s*(?P<mode>[^|]+)\s*\|\s*(?P<ip>[^|]+)\s*\|\s*Step:\s*(?P<step>[^|]+)\s*\|\s*Response:\s*(?P<response>[^|]+)\s*\|\s*RTT:\s*(?P<rtt>[^|]+)\s*\|?\s*(?P<rest>.*)$")
    domains = OrderedDict()  # domain -> list of hop entries (ip, rtt_ms, response)

    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            m = entry_re.match(line.strip())
            if not m:
                continue
            domain = m.group('domain').strip()
            ip = m.group('ip').strip()
            rtt_raw = m.group('rtt').strip()
            response = m.group('response').strip()
            # convert rtt to float ms if possible
            rtt_ms = None
            if rtt_raw != '-' and rtt_raw.lower() != ' -':
                # rtt like '189.14 ms' or '189.14'
                try:
                    rtt_ms = float(rtt_raw.split()[0])
                except Exception:
                    try:
                        rtt_ms = float(rtt_raw)
                    except Exception:
                        rtt_ms = None

            domains.setdefault(domain, []).append({'ip': ip, 'rtt': rtt_ms, 'response': response})

    return domains

def metrics_for_first_n(domains, n=10):
    items = list(domains.items())[:n]
    results = []
    for domain, hops in items:
        # count unique servers visited (unique IPs) in this query
        unique_ips = []
        for h in hops:
            if h['ip'] not in unique_ips:
                unique_ips.append(h['ip'])
        server_count = len(unique_ips)
        # compute overall latency for the query: sum of RTTs for hops that have rtt
        rtts = [h['rtt'] for h in hops if h['rtt'] is not None]
        total_latency = sum(rtts) if rtts else None
        # also compute median/mean if desired
        results.append({'domain': domain, 'servers_visited': server_count, 'total_latency_ms': total_latency, 'per_hop_rtts': rtts})
    return results

def plot_metrics(results, out_dir='plots'):
    os.makedirs(out_dir, exist_ok=True)
    domains = [r['domain'] for r in results]
    server_counts = [r['servers_visited'] for r in results]
    latencies = [r['total_latency_ms'] if r['total_latency_ms'] is not None else 0 for r in results]

    # Bar chart: servers visited
    plt.figure(figsize=(10,5))
    bars = plt.bar(range(len(domains)), server_counts, color='C0')
    plt.xticks(range(len(domains)), domains, rotation=45, ha='right')
    plt.ylabel('Unique DNS servers visited')
    plt.title('PCAP_1_H1 — DNS servers visited (first {})'.format(len(domains)))
    plt.tight_layout()
    servers_path = os.path.join(out_dir, 'h1_dns_servers_visited.png')
    plt.savefig(servers_path)
    plt.close()

    # Bar/line chart: latency per query
    plt.figure(figsize=(10,5))
    plt.bar(range(len(domains)), latencies, color='C1', alpha=0.8, label='Total RTT (ms)')
    plt.plot(range(len(domains)), latencies, color='C3', marker='o')
    plt.xticks(range(len(domains)), domains, rotation=45, ha='right')
    plt.ylabel('Total latency (ms)')
    plt.title('PCAP_1_H1 — Total latency per query (first {})'.format(len(domains)))
    plt.legend()
    plt.tight_layout()
    latency_path = os.path.join(out_dir, 'h1_dns_total_latency.png')
    plt.savefig(latency_path)
    plt.close()

    return servers_path, latency_path

def main():
    domains = parse_log(LOG_PATH)
    if not domains:
        print('No entries found in', LOG_PATH)
        return
    results = metrics_for_first_n(domains, n=10)
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['domain']}: servers_visited={r['servers_visited']}, total_latency_ms={r['total_latency_ms']}")

    servers_path, latency_path = plot_metrics(results)
    print('Plots written:')
    print(' -', servers_path)
    print(' -', latency_path)

if __name__ == '__main__':
    main()
