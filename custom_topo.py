from mininet.net import Mininet
from mininet.node import Node
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.topo import Topo
from mininet.nodelib import NAT


class CustomTopo(Topo):
    """Custom Mininet topology with four hosts, four switches, and one DNS relay."""
    
    def build(self):
        # Add hosts
        hosts = {
            f'H{i}': self.addHost(f'H{i}', ip=f'10.0.0.{i}/24')
            for i in range(1, 5)
        }
        dns = self.addHost('dns', ip='10.0.0.5/24')

        # Add switches
        switches = {
            f'S{i}': self.addSwitch(f'S{i}')
            for i in range(1, 5)
        }

        # Host-to-switch links
        host_link_params = dict(bw=100, delay='2ms')
        for i, h in enumerate(hosts.values(), start=1):
            self.addLink(h, switches[f'S{i}'], cls=TCLink, **host_link_params)

        # Inter-switch links
        inter_switch_links = [
            ('S1', 'S2', '5ms'),
            ('S2', 'S3', '8ms'),
            ('S3', 'S4', '10ms')
        ]
        for s1, s2, delay in inter_switch_links:
            self.addLink(switches[s1], switches[s2], cls=TCLink, bw=100, delay=delay)

        # DNS relay link
        self.addLink(dns, switches['S2'], cls=TCLink, bw=100, delay='1ms')


def topo():
    """Return topology instance for Mininet."""
    return CustomTopo()


topos = {'lin4': topo}


def run():
    """Run the custom Mininet topology with NAT and DNS forwarding."""
    topo = CustomTopo()
    net = Mininet(topo=topo, link=TCLink)

    info('*** Adding NAT for DNS forwarding\n')
    nat = net.addNAT(name='nat', connectTo='S2')
    nat.configDefault()

    # Configure NAT to forward DNS requests (UDP/TCP port 53)
    for proto in ['udp', 'tcp']:
        nat.cmd(f'iptables -t nat -A PREROUTING -p {proto} --dport 53 -j DNAT --to-destination 10.0.0.6:53')
        nat.cmd(f'iptables -A FORWARD -p {proto} -d 10.0.0.6 --dport 53 -j ACCEPT')

    net.start()
    info('*** Network configured. Ready for testing.\n')
    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
