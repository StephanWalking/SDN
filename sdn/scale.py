#!/usr/bin/env python3
import sys, time
from mininet.cli import CLI
from mininet.log import setLogLevel
from topo import build, configure_nat

N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
per = N // 4

setLogLevel('debug')
net = build()

# (switch, subnet-prefix, gateway, naamtag)
groups = [('sA1', '10.10.1', '10.10.0.254', 'eA'),
          ('sB1', '10.10.2', '10.10.0.254', 'eB'),
          ('sA2', '10.20.1', '10.20.0.254', 'gA'),
          ('sB3', '10.20.2', '10.20.0.254', 'gB')]
hosts = []
for sw, prefix, gw, tag in groups:
    for i in range(per):
        h = net.addHost(f'{tag}{i+1}', ip=f'{prefix}.{i+1}/22')
        net.addLink(h, net.get(sw))
        hosts.append((h, gw))

net.start()
configure_nat(net)
for h, gw in hosts:
    h.cmd(f'ip route add default via {gw}')
print('*** Wachten tot Faucet alle switches heeft geconfigureerd')
time.sleep(60)

print(f'*** {len(hosts)} hosts pingen tegelijk naar 203.0.113.1')
for h, _ in hosts:
    h.cmd(f'ping -c 20 -W 2 203.0.113.1 > /tmp/p_{h.name}.txt 2>&1 &')
time.sleep(5)
print('*** NAT-verbindingen (conntrack):', net.get('nat').cmd('conntrack -C').strip())
time.sleep(25)

ok = sum(1 for h, _ in hosts
         if ' 0% packet loss' in open(f'/tmp/p_{h.name}.txt').read())
print(f'*** RESULTAAT: {ok} van {len(hosts)} hosts hadden 0% packet loss')

CLI(net)
net.stop()
