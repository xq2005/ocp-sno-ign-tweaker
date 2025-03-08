import json
import base64
import argparse
import os
import base64
import yaml
import copy
import shutil 
from typing import Dict, List, Tuple

# /etc/hostname  owner: root   mod: 420(0644)
# /etc/NetworkManager/system-connections/*     owner: root    mod: 384(0600)
# /etc/dnsmasq.d/sno.conf  owner: root mod: 420(0644)

# 常量，用于存储系统文件的所有者和权限模式
# constants, for system file ownership and permission modes
SYSTEM_FILE_OWNER = "root"
MODE_0644 = 420
MODE_0600 = 384

# 目录和文件路径常量
# Constants for directory and file paths
CONNECTION_FULL_PATH_PREFIX = "/etc/NetworkManager/system-connections/"
BOOTSTRAP_CONNECTION_FULL_PATH_PREFIX = "/opt/openshift/sno_added/"
ETC_PATH = "/etc/"
MASTER_HOSTS_FILE_NAME = "master_hosts.conf"
OCP_HOSTS_FILE_NAME = "ocp.conf"
DNSMASQ_CONFD_PATH = "/etc/dnsmasq.d/"

# 定义 dnsmasq systemd 服务配置
# Define dnsmasq systemd service configuration
DNSMQSQ_SERVICE_SYSTEMD_UNIT = {
    "name": "dnsmasq.service",
"enabled": True,
"contents": """[Unit]
Description=DNS caching server.
After=network.target
[Service]
ExecStart=/usr/sbin/dnsmasq -k
Restart=on-failure
[Install]
WantedBy=multi-user.target
"""
}

# 定义一个继承自 str 的类，用于标识需要块格式的字符串
# Define a string subclass to allow YAML to store strings in block format
class BlockString(str):
    pass

# 定义一个表示器，将 BlockString 类型的对象以块格式表示
def block_string_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')

# 注册表示器, YAML 解析器使用块格式表示 BlockString
# Register YAML representer
yaml.add_representer(BlockString, block_string_representer)

# 解析命令行参数
# parse command line arguments
def ParseArguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Modify the OpenShift installer-generated SNO Ignition file to \nenable single-node installation without DHCP and external DNS server.", 
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--ign_file_path", 
                        required=True, 
                        help="Path to the Ignition JSON configuration file.")
    parser.add_argument("--network_file", 
                        action="append", 
                        required=True, 
                        help="Path to a network configuration file. Can be used multiple times")
    parser.add_argument("--hostname", 
                        required=False, 
                        help="FQDN Hostname and IPv4 address. \nFormat: <hostname>@<IPv4 address>")
    parser.add_argument("--extra_host", 
                        action="append", 
                        required=False, 
                        help="Additional hostname and IPv4 address pair (e.g., for an NFS server or private registry).\nCan be used multiple times.\nFormat: <hostname>@<IPv4 address> (e.g., nfsserver.sno.com@172.168.0.0.16).")
    return parser.parse_args()

# 检查文件是否存在
# Check if the file exists
def CheckFileExistence(file_path: str, file_type: str) -> None:
    if not os.path.isfile(file_path):
        print(f"Error: The specified {file_type} file '{file_path}' does not exist.")
        exit(1)

# 检查多个网络配置文件是否存在
# Check if multiple network configuration files exist
def CheckNetworkFiles(network_files: List[str]) :
    for net_file in network_files:
        CheckFileExistence(net_file, "network")

# 解析并读取 Ignition JSON 配置文件
# Parse and read the Ignition JSON configuration file
def DecodeIgnitionFile(ign_file_path: str) -> Dict:
    CheckFileExistence(ign_file_path, "Ignition")
    try:
        with open(ign_file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error: Failed to read or parse the Ignition file '{ign_file_path}': {e}")
        exit(1)

# 解析主机名和 IP 地址对（格式 <hostname>@<IPv4 address>）
# Parse hostname and IP address pair
def ParseHostnameIpPair(hn_with_ip:str) -> Tuple[str,str]:
    tokens = hn_with_ip.split("@")
    if len(tokens) != 2:
        print(f"hostname <{hn_with_ip}> format error.")
        exit(1)
    return (tokens[0], tokens[1])

# 从 Ignition 文件中提取集群域名和名称
# Extract domain name and cluster name from the Ignition file
def ExtractDomainAndClusterName(ign_data: Dict) -> Tuple[str, str]:
    for fileobj in ign_data["storage"]["files"]:
        if fileobj["path"].find("cluster-config.yaml") >= 0:
            file_source = fileobj["contents"]["source"]
            delimiter_pos = file_source.find(",")
            if delimiter_pos < 0:
                return ("", "")
            
            debase64_content = file_source[delimiter_pos+1:]
            if len(debase64_content) <= 0:
                print("Can not get <cluster-config.yaml>'s content.")
                exit(1)
            content_str = base64.b64decode(debase64_content)
            try:
                content_yaml = yaml.safe_load(content_str)
                install_config_str = content_yaml["data"]["install-config"]
                install_config_yaml = yaml.safe_load(install_config_str)
                return (install_config_yaml["baseDomain"], install_config_yaml["metadata"]["name"])
            except yaml.YAMLError as e:
                print(f"Extract Domain Name and Cluster Name fialed.: {e}")
                exit(1)

# 生成 Ignition 文件条目
# Generate an Ignition file entry
def CreateIgnitionFileEntry(file_path: str, content:str, file_mode: int) -> Dict:
    file_obj = {}
    file_obj["overwrite"] = True
    file_obj["path"] = file_path
    file_obj["user"] = {"name": SYSTEM_FILE_OWNER}
    file_obj["mode"] = file_mode

    source_str = "data:text/plain;charset=utf-8;base64," + base64.b64encode(content.encode('utf-8')).decode("utf-8")
    file_obj["contents"] = {"source": source_str}

    return file_obj

# 添加 master 主机名记录到 Ignition 配置
# Add master hostname record to the Ignition configuration
def AppendMasterHosts(ign_obj: Dict, hn_fqdn:str, ip_address:str):
    original_plain = f"{ip_address} {hn_fqdn} \n"
    tmp_path = ETC_PATH + MASTER_HOSTS_FILE_NAME
    ign_obj["storage"]["files"].append(CreateIgnitionFileEntry(tmp_path, original_plain, MODE_0644))
    tmp_path = BOOTSTRAP_CONNECTION_FULL_PATH_PREFIX + MASTER_HOSTS_FILE_NAME
    ign_obj["storage"]["files"].append(CreateIgnitionFileEntry(tmp_path, original_plain, MODE_0644))

# 读取网络管理器配置文件并添加到 Ignition
# Read NetworkManager configuration files and add them to the Ignition
def AppendConnectionFiles(connection_files: List[str], ign_obj: Dict):
    for cf_path in connection_files:
        cf_name = os.path.basename(cf_path)
        try:
            with open(cf_path, mode="r", encoding='utf-8') as cf:
                new_path = CONNECTION_FULL_PATH_PREFIX + cf_name
                content = cf.read()
                ign_obj["storage"]["files"].append(CreateIgnitionFileEntry(new_path, content, MODE_0600))
        except Exception as e:
            print(f"Error: Failed to read or encode the network file '{cf_path}': {e}")
            exit(1)

# 生成 OCP所需的主机解析配置内容。
# Generate the required host resolution configuration for OCP.
def GenerateOcpHostsContent(extra_hosts:List[str] | None, master_ip:str, domain_name:str, cluster_name:str) -> str:
    original_plain = ""

    # ocp needed hostname
    for prefix in ("apps", "api-int", "api", "ocp"):
        original_plain += f"address=/{prefix}.{cluster_name}.{domain_name}/{master_ip}\n"

    if extra_hosts:
        for extra_host in extra_hosts:
            hostname, ip_addr = ParseHostnameIpPair(extra_host)
            original_plain += f"address=/{hostname}/{ip_addr}\n"

    master_hosts_conf = ETC_PATH + MASTER_HOSTS_FILE_NAME
    original_plain += f"\naddn-hosts={master_hosts_conf}\n"

    original_plain += f"listen-address={master_ip}\n"

    return original_plain

# OCP主机配置添加到ignition文件
# Add OCP host configuration to the Ignition file.
def AppendOcpHosts(ign_obj: Dict, extra_hosts: List[str] | None, master_ip:str, domain_name:str, cluster_name:str):
    content = GenerateOcpHostsContent(extra_hosts, master_ip, domain_name, cluster_name)
    new_path = DNSMASQ_CONFD_PATH + OCP_HOSTS_FILE_NAME
    ign_obj["storage"]["files"].append(CreateIgnitionFileEntry(new_path, content, MODE_0644))
    new_path = BOOTSTRAP_CONNECTION_FULL_PATH_PREFIX + OCP_HOSTS_FILE_NAME
    ign_obj["storage"]["files"].append(CreateIgnitionFileEntry(new_path, content, MODE_0644))

# 添加启动dnsmasq服务到ignintion
# Add dnsmasq auto start configuration into Ignition file.
def AppendDnsmasqServie(ign_obj: Dict):
    ign_obj["systemd"]["units"].append(DNSMQSQ_SERVICE_SYSTEMD_UNIT)

# 更新 master-update.fcc 配置，确保 DNS 配置生效
# Update the master-update.fcc configuration to ensure that the DNS configuration takes effect.
def UpdateMasterFcc(ign_obj: Dict):
    for fileobj in ign_obj["storage"]["files"]:
        if fileobj["path"].find("master-update.fcc") >= 0:
            source_str = fileobj["contents"]["source"]
            tokens = source_str.split(",")
            yaml_obj = yaml.safe_load(base64.b64decode(tokens[1]).decode('utf-8'))

            # adding copy dnsmasq conf part into yaml object
            dnsmasq_update_obj = {
                "path": DNSMASQ_CONFD_PATH + OCP_HOSTS_FILE_NAME,
                "contents": {
                    "local": "sno_added/" + OCP_HOSTS_FILE_NAME
                },
                "mode": MODE_0644
            }
            yaml_obj["storage"]["files"].append(dnsmasq_update_obj)

            # copy MASTER_HOSTS_CONF
            master_hosts_obj = {
                "path": ETC_PATH + MASTER_HOSTS_FILE_NAME,
                "contents": {
                    "local": "sno_added/" + MASTER_HOSTS_FILE_NAME
                },
                "mode": MODE_0644,
                "overwrite": True
            }
            yaml_obj["storage"]["files"].append(master_hosts_obj)

            # enabling dnsmasq service
            yaml_obj["systemd"]["units"].append(copy.deepcopy(DNSMQSQ_SERVICE_SYSTEMD_UNIT))

            # keep '|' in yaml style
            for u_obj in yaml_obj["systemd"]["units"]:
                u_obj["contents"] = BlockString(u_obj["contents"])
            yaml_str = yaml.dump(yaml_obj, default_flow_style=False, allow_unicode=True)

            # 替换原有的source
            fileobj["contents"]["source"] = tokens[0] + "," + base64.b64encode(yaml_str.encode('utf-8')).decode("utf-8")
            
            break

# 输出修改后的 Ignition 文件到 edit.ign
# Dump modified Ignition file into edit.ign
def DumpEditIgn(original_ign_path: str, ign_obj: Dict):
    backup_file_path = original_ign_path + ".bak"
    if not os.path.exists(backup_file_path):
        shutil.copyfile(original_ign_path, backup_file_path)

    with open(original_ign_path, mode='w', encoding='utf-8') as ef:
        json.dump(ign_obj, ef, ensure_ascii=False, indent=2)

def main() -> None:
    args: argparse.Namespace = ParseArguments()
    CheckNetworkFiles(args.network_file)
    ign_data: Dict = DecodeIgnitionFile(args.ign_file_path)

    domain_name, cluster_name = ExtractDomainAndClusterName(ign_data)
    if len(domain_name) <= 0 or len(cluster_name) <= 0:
        print(f"Domain Name and Cluster Name must be defined in install_config.yaml")
        exit(1)

    # 添加网络配置
    # Add connetion files for network configuration
    AppendConnectionFiles(args.network_file, ign_data)

    # 添加NDS相关配置
    # Add dnsmasq conf
    if args.hostname:
        hostname, ip_addr = ParseHostnameIpPair(args.hostname)
        AppendMasterHosts(ign_data, hostname, ip_addr)
        AppendOcpHosts(ign_data, args.extra_host, ip_addr, domain_name, cluster_name)

        # 添加 dnsmasq服务配置
        # Add dnsmasq service conf
        AppendDnsmasqServie(ign_data)

        # 更新masterupdate.fcc
        # Update masterupdate.fc
        UpdateMasterFcc(ign_data)    
    
    # 备份ignition, 生成新的ignition
    # backup ignition, Create new ignition
    DumpEditIgn(args.ign_file_path, ign_data)

if __name__ == "__main__":
    main()