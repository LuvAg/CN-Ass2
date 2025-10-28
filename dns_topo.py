from mininet.net import Mininet
from mininet.node import Controller, OVSSwitch
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI
import time, os

# -------------------------------
# Utility function: Add NAT for internet access
# -------------------------------
def addNATandInternet(net, switch):
    info('*** Adding NAT for Internet access\n')
    nat = net.addNAT(name='nat', connectTo=switch)
    net.start()
    nat.configDefault()
    info('*** NAT configured (connected to %s)\n' % switch)
    return nat

# -------------------------------
# DNS lookup test function
# -------------------------------
def dns_test(host, url_file, save_dir):
    """
    Perform DNS lookups from url_file inside host.
    Save per-URL results to save_dir/results_<host>.txt
    Returns: (avg_latency_ms, throughput_qps, success, fail, total)
    """
    if not os.path.exists(url_file):
        info(f"WARNING: URL file {url_file} not found. Skipping {host.name}\n")
        return (0,0,0,0,0)

    host.cmd(f'cp {url_file} /tmp/urls.txt')
    result_file_host = f"/tmp/results_{host.name}.txt"
    result_file_vm = os.path.join(save_dir, f"results_{host.name}.txt")

    # Create script for DNS testing
    host.cmd(f'cat > /tmp/dns_test.sh <<\'EOF\'\n'
             '#!/bin/bash\n'
             'file=$1\n'
             f'output_file={result_file_host}\n'
             'success=0; fail=0; total_latency=0; count=0;\n'
             'start=$(date +%s)\n'
             'echo "" > $output_file\n'
             'while read url; do\n'
             '  [ -z "$url" ] && continue\n'
             '  t1=$(date +%s%3N)\n'
             '  # Try host VM DNS first, fallback to 8.8.8.8\n'
             '  nslookup $url > /dev/null 2>&1 || nslookup $url 8.8.8.8 > /dev/null 2>&1\n'
             '  if [ $? -eq 0 ]; then\n'
             '    t2=$(date +%s%3N)\n'
             '    latency=$((t2 - t1))\n'
             '    total_latency=$((total_latency + latency))\n'
             '    success=$((success + 1))\n'
             '    echo "$url → SUCCESS" >> $output_file\n'
             '  else\n'
             '    fail=$((fail + 1))\n'
             '    echo "$url → FAIL" >> $output_file\n'
             '  fi\n'
             '  count=$((count + 1))\n'
             'done < "$file"\n'
             'end=$(date +%s)\n'
             'duration=$((end - start)); [ $duration -eq 0 ] && duration=1\n'
             'if [ $success -gt 0 ]; then\n'
             '  avg=$((total_latency / success))\n'
             'else\n'
             '  avg=0\n'
             'fi\n'
             'throughput=$(echo "scale=2; $count / $duration" | bc)\n'
             'echo "$count $success $fail $avg $throughput" >> $output_file\n'
             'EOF')

    host.cmd('chmod +x /tmp/dns_test.sh')
    host.cmd('bash /tmp/dns_test.sh /tmp/urls.txt')

    # Copy result to VM folder
    host.cmd(f'cp {result_file_host} {result_file_vm}')

    # Read summary line for table
    summary = host.cmd(f'tail -n1 {result_file_host}').strip()
    try:
        total, success, fail, avg, thr = summary.split()
        return int(avg), float(thr), int(success), int(fail), int(total)
    except:
        return 0,0,0,0,0

# -------------------------------
# Build topology
# -------------------------------
def build_topology():
    setLogLevel('info')
    net = Mininet(controller=Controller, link=TCLink, switch=OVSSwitch)

    info('*** Adding controller\n')
    net.addController('c0')

    info('*** Adding switches\n')
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')
    s3 = net.addSwitch('s3')
    s4 = net.addSwitch('s4')

    info('*** Adding hosts\n')
    h1 = net.addHost('h1', ip='10.0.0.1/24')
    h2 = net.addHost('h2', ip='10.0.0.2/24')
    h3 = net.addHost('h3', ip='10.0.0.3/24')
    h4 = net.addHost('h4', ip='10.0.0.4/24')
    dns = net.addHost('dns', ip='10.0.0.5/24')

    info('*** Creating links\n')
    # Host to switch links
    net.addLink(h1, s1, bw=100, delay='2ms')
    net.addLink(h2, s2, bw=100, delay='2ms')
    net.addLink(h3, s3, bw=100, delay='2ms')
    net.addLink(h4, s4, bw=100, delay='2ms')
    # Switch interconnects
    net.addLink(s1, s2, bw=100, delay='5ms')
    net.addLink(s2, s3, bw=100, delay='8ms')
    net.addLink(s3, s4, bw=100, delay='10ms')
    # s2 to DNS host
    net.addLink(s2, dns, bw=100, delay='1ms')

    info('*** Starting network\n')
    net.start()

    # NAT for Internet access via s2
    addNATandInternet(net, s2)

    info('*** Testing connectivity\n')
    net.pingAll()

    # -----------------------
    # DNS TESTS
    # -----------------------
    save_dir = os.getcwd()  # save results in script folder
    hosts = [h1, h2, h3, h4]
    url_files = ['H1_domains_cleaned.txt', 'H2_domains_cleaned.txt', 'H3_domains_cleaned.txt', 'H4_domains_cleaned.txt']

    results = []
    for h, file in zip(hosts, url_files):
        res = dns_test(h, file, save_dir)
        results.append((h.name, *res))
        time.sleep(1)

    
    info('\n===== DNS Resolution Summary =====\n')
    print("{:<5} {:>10} {:>15} {:>10} {:>10} {:>12}".format(
        "Host", "AvgLatency(ms)", "Throughput(q/s)", "Success", "Fail", "Total"))
    for h, avg, thr, succ, fail, tot in results:
        print("{:<5} {:>10} {:>15} {:>10} {:>10} {:>12}".format(
            h, avg, thr, succ, fail, tot))
    print("==================================\n")

    # CLI for optional further testing
    CLI(net)
    net.stop()

# -------------------------------
if __name__ == '__main__':
    build_topology()
