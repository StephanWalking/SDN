#!/usr/bin/env python3
"""
Fase 2 Topologie:
- Dual-Stack (IPv4 /22 voor >500 users + IPv6 /64)
- Redundante Controllers
- NFV Stateful Firewalling (iptables & ip6tables via conntrack)
- IPv4 PAT/NAT Masquerading voor het /28 ISP-blok
- Userspace Datapath (netdev) voor OpenFlow 1.3 Meter ondersteuning
"""

import time
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel

def build():
    net = Mininet(controller=None, switch=OVSSwitch, autoSetMacs=True)

    # --- CONTROLLER REDUNDANTIE (Criterium 6: Level 4) ---
    c0 = net.addController('c0', controller=RemoteController, ip='172.17.0.1', port=6653)
    c1 = net.addController('c1', controller=RemoteController, ip='172.17.0.1', port=6654)

    # datapath='netdev' activeert userspace OVS waardoor OpenFlow 1.3 meters functioneren
    kw = dict(protocols='OpenFlow13', datapath='netdev')
    
    # Switches Gebouw A
    sA0 = net.addSwitch('sA0', dpid='0000000000000001', **kw)
    sA1 = net.addSwitch('sA1', dpid='0000000000000002', **kw)
    sA2 = net.addSwitch('sA2', dpid='0000000000000003', **kw)

    # Switches Gebouw B
    sB0 = net.addSwitch('sB0', dpid='0000000000000004', **kw)
    sB1 = net.addSwitch('sB1', dpid='0000000000000005', **kw)
    sB2 = net.addSwitch('sB2', dpid='0000000000000006', **kw)
    sB3 = net.addSwitch('sB3', dpid='0000000000000007', **kw)

    # Interne switchverbindingen (Uplinks)
    net.addLink(sA0, sA1)  # sA0-p1 <-> sA1-p1
    net.addLink(sA0, sA2)  # sA0-p2 <-> sA2-p1
    net.addLink(sB0, sB1)  # sB0-p1 <-> sB1-p1
    net.addLink(sB0, sB2)  # sB0-p2 <-> sB2-p1
    net.addLink(sB0, sB3)  # sB0-p3 <-> sB3-p1

    # Darkfiber trunk tussen Gebouw A en B
    net.addLink(sA0, sB0)  # sA0-p3 <-> sB0-p4

    # Endpoints toevoegen (/22 biedt ruimte aan >500 users)
    hosts_cfg = [
        ('hA1', sA1, '10.10.0.1/22'),   # Employee Gebouw A (MAC ...:01)
        ('hB1', sB1, '10.10.0.2/22'),   # Employee Gebouw B (MAC ...:02)
        ('hA2', sA2, '10.20.0.1/22'),   # Gast Gebouw A     (MAC ...:03)
        ('hB3', sB3, '10.20.0.2/22'),   # Gast Gebouw B     (MAC ...:04)
        ('hB2', sB2, '10.30.0.1/24')    # Beheer Gebouw B   (MAC ...:05)
    ]

    for name, sw, ip in hosts_cfg:
        h = net.addHost(name, ip=ip)
        net.addLink(h, sw)

    # Externe Routers & ISP simulatie
    # Gebouw A
    natA = net.addHost('natA', ip=None)
    inetA = net.addHost('inetA', ip='203.0.113.1/28')
    net.addLink(natA, sA0)    # natA-eth0 <-> sA0-p4 (VLAN 10 Employee)
    net.addLink(natA, sA0)    # natA-eth1 <-> sA0-p5 (VLAN 20 Gast)
    net.addLink(natA, sA0)    # natA-eth2 <-> sA0-p6 (VLAN 30 Mgmt)
    net.addLink(natA, inetA)  # natA-eth3 <-> inetA-eth0 (WAN Uplink ISP A)

    # Gebouw B
    natB = net.addHost('natB', ip=None)
    inetB = net.addHost('inetB', ip='203.0.113.17/28')
    net.addLink(natB, sB0)    # natB-eth0 <-> sB0-p5 (VLAN 10 Employee)
    net.addLink(natB, sB0)    # natB-eth1 <-> sB0-p6 (VLAN 20 Gast)
    net.addLink(natB, sB0)    # natB-eth2 <-> sB0-p7 (VLAN 30 Mgmt)
    net.addLink(natB, inetB)  # natB-eth3 <-> inetB-eth0 (WAN Uplink ISP B)

    return net

def configure_network(net):
    print("*** Netwerk configureren en wachten op switch initialisatie...")
    time.sleep(2)

    natA = net.get('natA')
    natB = net.get('natB')

    # Vaste MAC-adressen instellen op gast-gateways (gebruikt door Faucet voor Client-Isolatie)
    natA.cmd('ip link set dev natA-eth1 address 00:00:00:00:aa:20')
    natB.cmd('ip link set dev natB-eth1 address 00:00:00:00:bb:20')

    # IPv6 Adressen toekennen aan hosts
    net.get('hA1').cmd('ip -6 addr add 2001:db8:10::1/64 dev hA1-eth0')
    net.get('hB1').cmd('ip -6 addr add 2001:db8:10::2/64 dev hB1-eth0')
    net.get('hA2').cmd('ip -6 addr add 2001:db8:20::1/64 dev hA2-eth0')
    net.get('hB3').cmd('ip -6 addr add 2001:db8:20::2/64 dev hB3-eth0')
    net.get('hB2').cmd('ip -6 addr add 2001:db8:30::1/64 dev hB2-eth0')

    # Router A (Gebouw A) Adressen
    natA.cmd('ip addr add 10.10.0.254/22 dev natA-eth0')
    natA.cmd('ip addr add 10.20.0.254/22 dev natA-eth1')
    natA.cmd('ip addr add 10.30.0.254/24 dev natA-eth2')
    natA.cmd('ip addr add 203.0.113.2/28 dev natA-eth3')
    natA.cmd('ip -6 addr add 2001:db8:10::fe/64 dev natA-eth0')
    natA.cmd('ip -6 addr add 2001:db8:20::fe/64 dev natA-eth1')
    natA.cmd('ip -6 addr add 2001:db8:30::fe/64 dev natA-eth2')
    natA.cmd('ip -6 addr add 2001:db8:a::2/64 dev natA-eth3')

    # Router B (Gebouw B) Adressen
    natB.cmd('ip addr add 10.10.0.253/22 dev natB-eth0')
    natB.cmd('ip addr add 10.20.0.253/22 dev natB-eth1')
    natB.cmd('ip addr add 10.30.0.253/24 dev natB-eth2')
    natB.cmd('ip addr add 203.0.113.18/28 dev natB-eth3')
    natB.cmd('ip -6 addr add 2001:db8:10::fd/64 dev natB-eth0')
    natB.cmd('ip -6 addr add 2001:db8:20::fd/64 dev natB-eth1')
    natB.cmd('ip -6 addr add 2001:db8:30::fd/64 dev natB-eth2')
    natB.cmd('ip -6 addr add 2001:db8:b::2/64 dev natB-eth3')

    # Stateful Firewalls + Conntrack Tuning (>500 gebruikers)
    for rtr in [natA, natB]:
        w_if = f'{rtr.name}-eth3'
        rtr.cmd('sysctl -w net.ipv4.ip_forward=1')
        rtr.cmd('sysctl -w net.ipv6.conf.all.forwarding=1')
        rtr.cmd('sysctl -w net.netfilter.nf_conntrack_max=65536')
        rtr.cmd('sysctl -w net.ipv4.neigh.default.gc_thresh3=4096')
        rtr.cmd('sysctl -w net.ipv6.neigh.default.gc_thresh3=4096')

        # 1. IPv4 Stateful Firewall & NAT/PAT Masquerading
        rtr.cmd('iptables -F && iptables -t nat -F')
        rtr.cmd('iptables -P FORWARD DROP')
        rtr.cmd('iptables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT')
        for i in range(3):
            rtr.cmd(f'iptables -A FORWARD -i {rtr.name}-eth{i} -o {w_if} -m conntrack --ctstate NEW -j ACCEPT')
        rtr.cmd(f'iptables -t nat -A POSTROUTING -o {w_if} -j MASQUERADE')

        # 2. IPv6 Stateful Firewall (Zonder NAT)
        rtr.cmd('ip6tables -F')
        rtr.cmd('ip6tables -P FORWARD DROP')
        rtr.cmd('ip6tables -A FORWARD -p ipv6-icmp -m icmp6 --icmpv6-type destination-unreachable -j ACCEPT')
        rtr.cmd('ip6tables -A FORWARD -p ipv6-icmp -m icmp6 --icmpv6-type packet-too-big -j ACCEPT')
        rtr.cmd('ip6tables -A FORWARD -p ipv6-icmp -m icmp6 --icmpv6-type time-exceeded -j ACCEPT')
        rtr.cmd('ip6tables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT')
        for i in range(3):
            rtr.cmd(f'ip6tables -A FORWARD -i {rtr.name}-eth{i} -o {w_if} -m conntrack --ctstate NEW -j ACCEPT')

    # ISP Routes terug naar de interne IPv6-subnetten
    inetA = net.get('inetA')
    inetA.cmd('ip -6 addr add 2001:db8:a::1/64 dev inetA-eth0')
    inetA.cmd('ip route add default via 203.0.113.2')
    for vlan_id in ['10', '20', '30']:
        inetA.cmd(f'ip -6 route add 2001:db8:{vlan_id}::/64 via 2001:db8:a::2')

    inetB = net.get('inetB')
    inetB.cmd('ip -6 addr add 2001:db8:b::1/64 dev inetB-eth0')
    inetB.cmd('ip route add default via 203.0.113.18')
    for vlan_id in ['10', '20', '30']:
        inetB.cmd(f'ip -6 route add 2001:db8:{vlan_id}::/64 via 2001:db8:b::2')

    # Default Gateways op de hosts
    net.get('hA1').cmd('ip route add default via 10.10.0.254')
    net.get('hA1').cmd('ip -6 route add default via 2001:db8:10::fe')
    net.get('hA2').cmd('ip route add default via 10.20.0.254')
    net.get('hA2').cmd('ip -6 route add default via 2001:db8:20::fe')

    net.get('hB1').cmd('ip route add default via 10.10.0.253')
    net.get('hB1').cmd('ip -6 route add default via 2001:db8:10::fd')
    net.get('hB3').cmd('ip route add default via 10.20.0.253')
    net.get('hB3').cmd('ip -6 route add default via 2001:db8:20::fd')
    net.get('hB2').cmd('ip route add default via 10.30.0.253')
    net.get('hB2').cmd('ip -6 route add default via 2001:db8:30::fd')

if __name__ == '__main__':
    setLogLevel('info')
    net = build()
    net.start()

    controllers = [net.get('c0'), net.get('c1')]
    for sw in net.switches:
        sw.start(controllers)

    configure_network(net)
    print("\n--- Fase 2 Netwerk gereed (Dual Controllers actief). Start CLI ---")
    CLI(net)
    net.stop()
