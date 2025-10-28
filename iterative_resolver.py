"""Iterative DNS resolver server

This module implements an iterative-style DNS resolver that queries root/TLD/
authoritative servers step-by-step. It is a cleaned-up version of the prior
`custom_dns.py` with renamed symbols and expanded inline comments.
"""
import socket
import time
import sys
from dnslib import DNSRecord


# Default root servers used for bootstrap
ROOT_NS = [
    '198.41.0.4',
    '199.9.14.201',
    '192.33.4.12',
]


def resolve_iteratively(query_bytes):
    """Perform iterative resolution for one DNS query.

    Returns: (response_bytes or None, step_log (list), total_ms, queried_name)
    """
    query = DNSRecord.parse(query_bytes)
    qname = str(query.q.qname)

    timeline = []
    start = time.time()
    current_ns = ROOT_NS[:]
    response_payload = None
    step_idx = 0

    # Continue until we get an answer or cannot proceed
    while True:
        step_idx += 1
        responded = False
        used_server = None
        got_data = None

        for server in current_ns:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(2)
                t0 = time.time()
                try:
                    s.sendto(query_bytes, (server, 53))
                    got_data, _ = s.recvfrom(2048)
                    t1 = time.time()
                    rtt_ms = (t1 - t0) * 1000
                    responded = True
                    used_server = server
                    break
                except socket.timeout:
                    timeline.append({'step': step_idx, 'server': server, 'rtt': None, 'status': 'timeout'})

        if not responded:
            break

        parsed = DNSRecord.parse(got_data)

        # classify stage
        if step_idx == 1:
            stage = 'Root'
        elif parsed.auth and not parsed.rr:
            stage = 'TLD'
        else:
            stage = 'Authoritative'

        # summarize response
        records = parsed.rr or parsed.auth or []
        summary = []
        if records:
            for rr in records:
                summary.append(f"{rr.rname} -> {rr.rtype} -> {rr.rdata}")
        else:
            summary.append('Referral or empty')

        timeline.append({'step': step_idx, 'server': used_server, 'rtt': round(rtt_ms, 2), 'stage': stage, 'response': summary})

        if parsed.rr:
            response_payload = got_data
            break

        # attempt to extract IPs for next iteration
        next_ips = [str(rr.rdata) for rr in parsed.ar if rr.rtype == 1]
        if not next_ips:
            ns_names = [str(rr.rdata) for rr in parsed.auth if rr.rtype == 2]
            if ns_names:
                # try resolving nameserver names by recursive call
                resolved_ips = []
                for n in ns_names:
                    sub_q = DNSRecord.question(n)
                    sub_resp, sub_log, _, _ = resolve_iteratively(bytes(sub_q.pack()))
                    timeline.extend(sub_log)
                    if sub_resp:
                        p = DNSRecord.parse(sub_resp)
                        for rr in p.rr:
                            if rr.rtype == 1:
                                resolved_ips.append(str(rr.rdata))
                next_ips = resolved_ips

        if not next_ips:
            break

        current_ns = next_ips

    total_ms = (time.time() - start) * 1000
    return response_payload, timeline, round(total_ms, 2), qname


def run_server(logfile='resolver_log.txt'):
    """Run UDP server on 10.0.0.5:53 and write step logs to logfile."""
    with open(logfile, 'a') as out:
        def log_write(*args, **kwargs):
            print(*args, **kwargs)
            print(*args, **kwargs, file=out)
            out.flush()

        header = f"\n===== New Run at {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n"
        out.write(header)
        print(header.strip())

        log_write('Starting iterative resolver on 10.0.0.5:53')
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('10.0.0.5', 53))

        while True:
            try:
                data, addr = sock.recvfrom(512)
                recv_ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                resp, log, total, qname = resolve_iteratively(data)

                log_write(f"\n[{recv_ts}] Query from {addr[0]} for {qname}")
                for s in log:
                    log_write(f"  Step {s.get('step')} | Server: {s.get('server')} | Stage: {s.get('stage', 'N/A')} | RTT: {s.get('rtt')} ms")
                    log_write('    Response:')
                    for L in s.get('response', []):
                        log_write(f"      {L}")
                    log_write()

                log_write(f"  Total resolution time: {total} ms")

                if resp:
                    sock.sendto(resp, addr)
                else:
                    log_write('  Resolution failed.')

            except KeyboardInterrupt:
                log_write('\nShutting down resolver...')
                break
            except Exception as exc:
                log_write(f'Error: {exc}')
                continue


if __name__ == '__main__':
    logfile_arg = sys.argv[1] if len(sys.argv) > 1 else 'resolver_log.txt'
    run_server(logfile=logfile_arg)
