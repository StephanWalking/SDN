# Pure SDN Campus Fabric (Faucet & Open vSwitch)

Een Mininet-netwerkomgeving verdeeld over twee gebouwen (A en B), centraal bestuurd door redundante Faucet SDN-controllers over een gedistribueerde OpenFlow switch-stack.

---

## 1. Architectuuroverzicht

- **Pure SDN Implementatie:** Geen externe Linux-gateways of virtuele router-appliances (`natA`/`natB`). Alle L2 switching, L3 distributed routing, filtering en NAT worden direct door Open vSwitch afgehandeld onder aansturing van Faucet.
- **Dual-Stack Distributed L3 Routing:** Elk VLAN beschikt over een virtueel IPv4- en IPv6-gatewayadres (Faucet VIP) dat lokaal op alle switches beschikbaar is. Verkeer tussen VLAN's en richting het WAN wordt via OpenFlow FIB-flows gerouteerd (inclusief MAC-rewrites en TTL-decrements).
- **Stateful Firewall & NAT/PAT in OpenFlow:** Gebruik van OVS Conntrack- en NAT-extensies (`actions: ct: ... nat: ...`) direct in OpenFlow. Private IPv4-adressen worden dynamisch vertaald naar het toegekende publieke WAN-adres (`203.0.113.2` / `203.0.113.18`), waarmee de beperking van het `/28` WAN-blok voor >500 hosts wordt opgelost.
- **Gastenisolatie:** Verkeer vanuit het gastennetwerk (VLAN 20) wordt aan de netwerkrand via Faucet ACL `guest_isolation` geblokkeerd richting medegasten en interne subnetten (Employee/Management). Alleen uitgaand verkeer naar het internet is toegestaan.
- **QoS Rate Limiting:** Gastenverkeer naar het WAN wordt via OpenFlow 1.3 Meter 1 begrensd op 10 Mbit/s.
- **L2 Management Port Security:** Op de management-poort (`sB2-eth2`) laat de ACL `mgmt_portsec` uitsluitend het legitieme MAC-adres van beheer-host `hB2` (`00:00:00:00:00:05`) toe.
- **Controller Redundantie:** Twee Faucet-controllers (`c0` op poort 6653 en `c1` op poort 6654) zijn parallel verbonden met alle switches in de fabric.

---

## 2. Bestandenstructuur

| Bestand | Doel |
|---|---|
| `topo.py` | Mininet-topologie (OVS `netdev` datapaths, stacking links, darkfiber en ISP-endpoints) |
| `faucet.yaml` | Switch fabric stacking, VLAN's, L3 VIPs, ISP static routes en DP-interfaces |
| `acls.yaml` | OVS Conntrack/NAT flow rules, gastenisolatie, 10 Mbps meter en Port Security |

*De YAML-configuratiebestanden dienen geplaatst te worden in `/etc/faucet/`.*

---

## 3. Netwerkindeling en Adressering

### VLAN-structuur

| VLAN | Naam | IPv4 Subnet | IPv6 Subnet | Faucet Gateway (VIP) |
|---|---|---|---|---|
| 10 | Employee | `10.10.0.0/22` | `2001:db8:10::/64` | `10.10.0.254` / `2001:db8:10::fe` |
| 20 | Gast | `10.20.0.0/22` | `2001:db8:20::/64` | `10.20.0.254` / `2001:db8:20::fe` |
| 30 | Management | `10.30.0.0/24` | `2001:db8:30::/64` | `10.30.0.254` / `2001:db8:30::fe` |
| 100 | ISP WAN | `203.0.113.0/28` | `2001:db8:a::/64` & `b::/64` | Switch VIPs: `.2` (A) / `.18` (B) |

### Hostconfiguratie

| Host | Locatie | Switch-poort | VLAN | IP-adres | MAC-adres |
|---|---|---|---|---|---|
| `hA1` | Gebouw A (Vloer 1) | `sA1-eth2` | 10 | `10.10.0.1/22` | `00:00:00:00:00:01` |
| `hA2` | Gebouw A (Vloer 2) | `sA2-eth2` | 20 | `10.20.0.1/22` | `00:00:00:00:00:02` |
| `hB1` | Gebouw B (Vloer 1) | `sB1-eth2` | 10 | `10.10.0.2/22` | `00:00:00:00:00:03` |
| `hB2` | Gebouw B (Vloer 2) | `sB2-eth2` | 30 | `10.30.0.1/24` | `00:00:00:00:00:05` |
| `hB3` | Gebouw B (Vloer 3) | `sB3-eth2` | 20 | `10.20.0.2/22` | `00:00:00:00:00:04` |

* **ISP A:** `203.0.113.1` en `2001:db8:a::1` (verbonden met `sA0-eth1`)
* **ISP B:** `203.0.113.17` en `2001:db8:b::1` (verbonden met `sB0-eth1`)

---

## 4. Installatie en Uitvoering

1. **Start de Faucet controllers:**
   ```bash
   docker restart faucet faucet-b
   ```

2. **Start de Mininet-topologie:**
   ```bash
   sudo mn -c
   sudo python3 topo.py
   ```

3. **Verifieer controller-connectiviteit:**
   ```bash
   mininet> sh ovs-vsctl show
   ```
   *Controleer of onder alle switches beide controllers (`tcp:172.17.0.1:6653` en `tcp:172.17.0.1:6654`) de status `is_connected: true` vertonen.*

---

## 5. Testprocedures en Verificatie

Gebruik de flag `-c 3` voor compacte testuitvoer en `-W 1` bij tests die bedoeld zijn om te falen (packet drop).

### Functionaliteitstesten

| Functionaliteit | Testcommando in Mininet | Verwacht resultaat |
|---|---|---|
| Distributed Gateway IPv4 | `hA1 ping -c 2 10.10.0.254` | 0% packet loss |
| Distributed Gateway IPv6 | `hA1 ping6 -c 2 2001:db8:10::fe` | 0% packet loss (NDP beantwoord) |
| Inter-VLAN Routing over Stack | `hA1 ping -c 3 10.30.0.1` | 0% packet loss (na ARP), `ttl=63` |
| Inter-VLAN IPv6 Routing | `hA1 ping6 -c 3 2001:db8:30::1` | 0% packet loss, `ttl=63` |
| IPv4 WAN Routing via OVS NAT | `hA1 ping -c 3 203.0.113.1` | 0% packet loss, `ttl=63` |
| IPv6 WAN Routing | `hA1 ping6 -c 3 2001:db8:a::1` | 0% packet loss, `ttl=63` |
| Gastenisolatie (Client-to-Client) | `hA2 ping -c 2 -W 1 10.20.0.2` | 100% packet loss (Table 0 drop) |
| Gastenisolatie (naar Employee) | `hA2 ping -c 2 -W 1 10.10.0.1` | 100% packet loss (Table 0 drop) |
| Gastenisolatie (naar Management) | `hA2 ping -c 2 -W 1 10.30.0.1` | 100% packet loss (Table 0 drop) |
| Gasten WAN-toegang | `hA2 ping -c 3 203.0.113.1` | 0% packet loss |
| QoS Meter Validatie | `sh ovs-ofctl -O OpenFlow13 meter-stats sA2` | Actieve packet- en byte-telling op meter 1 |

### Verificatie van L2 Management Port Security
```bash
mininet> hB2 ping -c 2 10.30.0.254
mininet> hB2 ip link set dev hB2-eth0 address 00:00:00:00:99:99
mininet> hB2 ping -c 2 -W 1 10.30.0.254
mininet> hB2 ip link set dev hB2-eth0 address 00:00:00:00:00:05
mininet> hB2 ping -c 2 10.30.0.254
```
*Resultaat:* Met het geautoriseerde MAC (`...:05`) slaagt de ping. Met een gewijzigd MAC (`...:99`) treedt direct 100% packet loss op.

### Verificatie van OpenFlow NAT/PAT
Voer een live packet capture uit op de ISP-interface tijdens netwerkverkeer:
```bash
mininet> inetA tcpdump -n -i inetA-eth0 icmp &
mininet> hA1 ping -c 2 203.0.113.1
mininet> inetA kill %1
```
*Resultaat:* De ICMP requests arriveren bij `inetA` met source IP `203.0.113.2` in plaats van het private IP `10.10.0.1`.

---

## 6. Bewijslastverzameling (Portfolio / CGI)

Genereer flow- en meter-statistieken nadat de tests zijn uitgevoerd:

```bash
sh ovs-ofctl -O OpenFlow13 dump-flows sA1 > flows_sA1.txt
sh ovs-ofctl -O OpenFlow13 dump-flows sA0 > flows_sA0.txt
sh ovs-ofctl -O OpenFlow13 dump-flows sA2 > flows_sA2.txt
sh ovs-ofctl -O OpenFlow13 dump-flows sB2 > flows_sB2.txt
sh ovs-ofctl -O OpenFlow13 meter-stats sA2 > meter_sA2.txt
```

Te identificeren OpenFlow-constructies in de dumps:
- **Table 0 (ACL & Ingress Security):** Conntrack-classificatie (`ct_state`), MAC whitelisting en drop-rules voor gastverkeer.
- **Table 1 (VLAN Tagging & Classification):** 802.1Q toewijzing.
- **Table 2 / FIB (L3 Forwarding):** OpenFlow routing met `dec_ttl` en L2/L3 rewrites.
- **Conntrack NAT Actions:** Flows met `actions=ct(zone=1,nat(...))`.

---

## 7. Afsluiten

```bash
mininet> exit
sudo mn -c
```