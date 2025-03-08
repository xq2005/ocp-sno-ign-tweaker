# ocp-sno-ign-tweaker

<div align="center">
  <a href="./README.md"><img alt="README in 中文" src="https://img.shields.io/badge/简体中文-d9d9d9"></a>
  <a href="./README.EN.md"><img alt="README in English" src="https://img.shields.io/badge/English-d9d9d9"></a>
</div>
<br/>

⚠ **This project is for learning purposes only. Do not use it in a production environment.**

## Background

Red Hat OpenShift supports manual single-node (bare metal/virtual machine) installation. Please refer to the [official documentation](https://docs.openshift.com/container-platform/4.15/installing/installing_sno/install-sno-installing-sno.html#install-sno-installing-sno-manually) for detailed steps.

The installation process relies on an external DNS service. For detailed configuration, see [User-provisioned DNS requirements](https://docs.openshift.com/container-platform/4.15/installing/installing_bare_metal/installing-bare-metal-network-customizations.html#installation-dns-user-infra_installing-bare-metal-network-customizations). This means an additional host (bare metal/virtual machine) is required to provide DNS services for the installation to complete.

## Purpose

The script in this project enables single-node OpenShift installation using a static IP and its own DNS service. **It does not rely on external DNS and DHCP servers**, thereby simplifying resource requirements for deploying OpenShift in a single-node environment.

## Implementation

1. **Static IP**
   - Adds a network configuration file to the Ignition file, automatically configuring a static IP at startup, eliminating the need for a DHCP service.
2. **Built-in DNS**
   - CoreOS includes `dnsmasq`, which is disabled by default. This project modifies the Ignition file to add domain resolution rules required for single-node OpenShift and configures `dnsmasq` to start automatically, providing DNS services during the installation process.

## Script Usage

1. Complete **Steps 1-8** of the [official documentation](https://docs.openshift.com/container-platform/4.15/installing/installing_sno/install-sno-installing-sno.html#install-sno-installing-sno-manually).
2. Run the script (detailed parameter descriptions below):
   ```bash
   python ./sno_ign_tweaker.py \
   --ign_file_path ./ocp/bootstrap-in-place-for-live-iso.ign \
   --network_file ./Wired\ connection\ 1.nmconnection \
   --hostname master.sno.com@172.168.0.99
   ```
3. Continue with the remaining steps in the [official documentation](https://docs.openshift.com/container-platform/4.15/installing/installing_sno/install-sno-installing-sno.html#install-sno-installing-sno-manually).

## Script Parameter Description

```bash
[tt@fedora]$ python sno_ign_tweaker.py --help
usage: sno_ign_tweaker.py [-h] --ign_file_path IGN_FILE_PATH --network_file NETWORK_FILE [--hostname HOSTNAME]
                          [--extra_host EXTRA_HOST]

Modify the OpenShift installer-generated SNO Ignition file to
enable single-node installation without a DHCP and external DNS server.

options:
  -h, --help            Show this help message and exit.
  --ign_file_path IGN_FILE_PATH
                        Path to the Ignition JSON configuration file.
  --network_file NETWORK_FILE
                        Path to a network configuration file. Can be specified multiple times.
  --hostname HOSTNAME   FQDN hostname and IPv4 address.
                        Format: <hostname>@<IPv4 address>.
  --extra_host EXTRA_HOST
                        Additional hostname and IPv4 address pair (e.g., for an NFS server or private registry).
                        Can be specified multiple times.
                        Format: <hostname>@<IPv4 address> (e.g., nfsserver.sno.com@172.168.0.16).
```

- --ign_file_path IGN_FILE_PATH
  - **Description**: The `.ign` file generated in Step 8 of the official documentation. Default path: `ocp/bootstrap-in-place-for-live-iso.ign`.
- --network_file NETWORK_FILE
  - **Description**: The path to the network configuration file (see below for retrieval instructions).
  - **Note**: If multiple network interfaces or bond configurations exist, this parameter can be specified multiple times.
- --hostname HOSTNAME
  - **Description**: The **fully qualified domain name (FQDN)** and **IPv4 address** of the SNO host.
  - **Format**: `<hostname>@<IPv4 address>` (e.g., `master.sno.com@172.168.0.99`).
- --extra_host EXTRA_HOST
  - **Description**: Additional server hostnames and IPv4 addresses (e.g., for an NFS server or private registry).
  - **Format**: `<hostname>@<IPv4 address>` (e.g., `nfsserver.sno.com@172.168.0.16`).
  - **Note**: This parameter can be specified multiple times to provide multiple additional host entries.

## How to Obtain the Network Configuration File

1. Boot the host using the CoreOS Live ISO.
2. Configure the network using either [command-line ](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/configuring-an-ethernet-connection_configuring-and-managing-networking#configuring-an-ethernet-connection-by-using-nmcli_configuring-an-ethernet-connection)[`nmcli`](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/configuring-an-ethernet-connection_configuring-and-managing-networking#configuring-an-ethernet-connection-by-using-nmcli_configuring-an-ethernet-connection) or [graphical ](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/configuring-an-ethernet-connection_configuring-and-managing-networking#configuring-an-ethernet-connection-by-using-nmtui_configuring-an-ethernet-connection)[`nmtui`](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_and_managing_networking/configuring-an-ethernet-connection_configuring-and-managing-networking#configuring-an-ethernet-connection-by-using-nmtui_configuring-an-ethernet-connection), and ensure internet connectivity.
   > ⚠ **Important!**
   >
   > - Configure the local DNS address only on the network interface associated with the host’s IPv4 address.
   > - The **first DNS address** in the network config  uration **must be the local IP**.
3. Locate the network configuration file in `/etc/NetworkManager/system-connections/` and copy it to the image-building server using `scp`:
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

