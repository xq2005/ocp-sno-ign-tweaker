# ocp-sno-ign-tweaker

<div align="center">
  <a href="./README.md"><img alt="README in 中文" src="https://img.shields.io/badge/简体中文-d9d9d9"></a>
  <a href="./README.EN.md"><img alt="README in English" src="https://img.shields.io/badge/English-d9d9d9"></a>
</div>
<br/>

⚠ **本项目仅用于学习记录目的，请勿在生产环境中使用。**
**仅在OpenShift 4.15版本测试。** 

**背景**
RedHat OpenShift支持手动单节点（裸金属/虚拟机）安装，具体步骤参阅 [官方文档](https://docs.openshift.com/container-platform/4.15/installing/installing_sno/install-sno-installing-sno.html#install-sno-installing-sno-manually)。 安装过程依赖外置的DNS服务，详细配置参考 [用户自配置 DNS 要求](https://docs.openshift.com/container-platform/4.15/installing/installing_bare_metal/installing-bare-metal-network-customizations.html#installation-dns-user-infra_installing-bare-metal-network-customizations)。 这意味着仍然需要额外的主机（裸金属/虚拟机）提供 DNS 服务，才能完成安装。

**目的**
本项目中的脚本通过 静态IP + 自身DNS服务 完成单节点OpenShift的安装。**无需依赖外部 DNS 和 DHCP 服务器**，从而简化 OpenShift 单节点部署的资源需求。

**实现方法**
1. 静态IP
   在Ignition文件中添加网卡的配置文件，启动时自动配置静态IP，无需DHCP服务
2. 内置DNS
   CoreOS自带dnsmasq，默认不启动。在Ignition文件中，添加OpenShift单节点需要的域名解析规则，修改默认启动dnsmasq服务。安装过程中为OpenShift提供DNS服务。

**脚本使用方法**
1. 按照 [官方文档](https://docs.openshift.com/container-platform/4.15/installing/installing_sno/install-sno-installing-sno.html#install-sno-installing-sno-manually) 完成1-8步

2. 运行脚本 (详细参数说明见下方)
   ```bash
   python ./sno_ign_tweaker.py \
   --ign_file_path ./ocp/bootstrap-in-place-for-live-iso.ign \
   --network_file ./'Wired connection 1.nmconnection' \
   --hostname master.sno.com@172.168.0.99
   ```
   
3. 继续按照[官方文档](https://docs.openshift.com/container-platform/4.15/installing/installing_sno/install-sno-installing-sno.html#install-sno-installing-sno-manually) 完成后继步骤

**脚本参数说明**
```bash
[tt@fedora]$ python sno_ign_tweaker.py --help
usage: sno_ign_tweaker.py [-h] --ign_file_path IGN_FILE_PATH --network_file NETWORK_FILE [--hostname HOSTNAME]
                          [--extra_host EXTRA_HOST]

Modify the OpenShift installer-generated SNO Ignition file to
enable single-node installation without DHCP and external DNS server.

options:
  -h, --help            show this help message and exit
  --ign_file_path IGN_FILE_PATH
                        Path to the Ignition JSON configuration file.
  --network_file NETWORK_FILE
                        Path to a network configuration file. Can be used multiple times
  --hostname HOSTNAME   FQDN Hostname and IPv4 address.
                        Format: <hostname>@<IPv4 address>
  --extra_host EXTRA_HOST
                        Additional hostname and IPv4 address pair (e.g., for an NFS server or private registry).
                        Can be used multiple times.
                        Format: <hostname>@<IPv4 address> (e.g., nfsserver.sno.com@172.168.0.0.16).
```
- --ign_file_path IGN_FILE_PATH
  - **描述**：官方文档中第8步生成的.ign文件，默认路径`ocp/bootstrap-in-place-for-live-iso.ign`
- --network_file NETWORK_FILE
  - **描述**: 需要指定的网卡配置文件路径（如何获取见下方）。
  - **说明**：多块网卡或 bond 配置时，可多次指定该参数。
- --hostname HOSTNAME
  - **描述**: 安装 SNO 主机的 完整主机名 和 IPv4 地址.
  - **格式**：`<hostname>@<IPv4 address>`，例如 `master.sno.com@172.168.0.99`。
- --extra_host EXTRA_HOST
  - **描述**: 额外的服务器主机名和 IPv4 地址（如 NFS 服务器、私有镜像仓库）。
  - **格式**：格式`<hostname>@<IPv4 address>`，例如 `nfsserver.sno.com@172.168.0.16`。
  - **说明**可多次指定该参数，以提供多个额外主机信息。

**如何获取网卡配置文件**
1. 主机使用coreos live ISO 引导启动
2. 通过 [命令行 mcli](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/configuring-an-ethernet-connection_configuring-and-managing-networking#configuring-an-ethernet-connection-by-using-nmcli_configuring-an-ethernet-connection) 或者 [图形化 nmtui](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/configuring-an-ethernet-connection_configuring-and-managing-networking#configuring-an-ethernet-connection-by-using-nmtui_configuring-an-ethernet-connection) 配置网卡，并确保能正常访问外网：
   > ⚠ **注意！注意！注意！**
   > - 只在与主机IPv4对应的网卡配置本机DNS地址。
   > - 网卡中指定的第一DNS必须是 **`本机IP`**。
3. 在`/etc/NetworkManager/system-connections/`目录下找到网卡配置文件，并通过 scp 拷贝到镜像制作的服务器，供脚本 `sno_ign_tweaker.py`使用。

4. nmcli配置网卡与拷贝示例
  ```bash
  [core@localhost ~]$ nmcli connection show
  NAME                UUID                                  TYPE        DEVICE
  Wired connection 1  0ad464f7-0c95-383c-8e40-86efd3c0b40b  ethernet    eth0
  lo                  6d2b03c2-2b63-4bc6-9b2f-59747aa9e442  loopback    lo
  
  [core@localhost ~]$ sudo nmcli connection modify "Wired connection 1" ipv4.addresses "172.168.0.99/24" ipv4.gateway 172.168.0.1 ipv4.dns 172.168.0.99 +ipv4.dns 8.8.8.8 ipv4.method manual connection.autoconnect yes 
		
  [core@localhost ~]$ sudo nmcli connection reload
		
  [core@localhost ~]$ sudo nmcli connection up "Wired connection 1"
		
  [core@localhost ~]$ ping -c 4 cn.bing.com
  PING a-0001.a-msedge.net (204.79.197.200) 56(84) bytes of data.
  64 bytes from a-0001.a-msedge.net (204.79.197.200): icmp_seq=1 ttl=115 time=78.5 ms
  64 bytes from a-0001.a-msedge.net (204.79.197.200): icmp_seq=2 ttl=115 time=76.8 ms
  64 bytes from a-0001.a-msedge.net (204.79.197.200): icmp_seq=3 ttl=115 time=78.7 ms
  64 bytes from a-0001.a-msedge.net (204.79.197.200): icmp_seq=4 ttl=115 time=77.5 ms
  
  --- a-0001.a-msedge.net ping statistics ---
  4 packets transmitted, 4 received, 0% packet loss, time 3005ms
  rtt min/avg/max/mdev = 76.750/77.844/78.689/-.786 ms
  
  [core@localhost ~]$ sudo scp /etc/NetworkManager/system-connections/Wired\ connection\ 1.nmconnection test@172.168.0.10:/home/test/sno
  The authenticity of host '172.168.0.10 (172.168.0.10)' can't be established.
  ED25519 key fingerprint is SHA256:xo+SD0U74fZEoMBNeApYDhB7KI8ntrQR6uOdiEUTTtg.
  Are you sure you want to continue connecting (yes/no/[fingerprint]): yes
  Warning: Permanently added '172.168.0.10' (ED25519) to the list of known hosts.
  test@172.168.0.10's password:
  Wired connection 1.nmconnection                                           100%   303  614.5KB/s  00:00
  ```