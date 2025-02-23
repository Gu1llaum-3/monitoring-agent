#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import socket
import psutil
import requests
import logging
import json
import argparse
import netifaces
import shutil
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Vérifier et installer les dépendances avant de continuer
REQUIRED_PACKAGES = {"psutil": "python3-psutil", "requests": "python3-requests", "netifaces": "python3-netifaces"}

def is_package_installed(package_name):
    """ Vérifie si un package Python est installé """
    import importlib.util
    return importlib.util.find_spec(package_name) is not None

def install_packages(packages):
    """ Installe les packages manquants via apt """
    print("Installation via apt...")
    subprocess.check_call(["sudo", "apt-get", "install", "-y"] + packages)

def check_and_install_packages():
    """ Vérifie et installe les packages nécessaires """
    missing_packages = [pkg for pkg in REQUIRED_PACKAGES if not is_package_installed(pkg)]

    if missing_packages:
        print(f"Les paquets suivants sont requis mais non installés : {', '.join(missing_packages)}")
        install = input("Souhaitez-vous les installer maintenant ? (y/n): ").strip().lower()

        if install == 'y':
            package_names = [REQUIRED_PACKAGES[pkg] for pkg in missing_packages]
            install_packages(package_names)
            print("Installation terminée. Veuillez relancer le script.")
            sys.exit(0)
        else:
            print("Erreur : Certains paquets manquent, le script peut ne pas fonctionner correctement.")
            sys.exit(1)

# Vérifier et installer les dépendances avant importation des modules
check_and_install_packages()

# Configuration
CONFIG_FILE = "agent_config.json"
DEFAULT_CONFIG = {
    "server_url": None,
    "port": None,
    "interval": 1,
    "log_file": "/var/log/agent_monitor.log"
}

def setup_logging(log_file):
    """ Configure le logging avec rotation """
    log_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)
    log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    log_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    console_handler.setLevel(logging.INFO)

    logging.basicConfig(level=logging.INFO, handlers=[log_handler, console_handler])

def get_system_ip():
    """ Récupère l'adresse IP locale correcte """
    ip_address = None
    for iface in netifaces.interfaces():
        if iface.startswith(('lo', 'docker', 'br-')):
            continue
        addrs = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in addrs:
            for addr in addrs[netifaces.AF_INET]:
                ip = addr['addr']
                if not ip.startswith(('127.', '169.254.')):
                    ip_address = ip
                    break
        if ip_address:
            break
    return ip_address if ip_address else socket.gethostbyname(socket.gethostname())

def get_update_metrics():
    """ Collecte les métriques de mises à jour système """
    try:
        # Vérifier le nombre total de paquets à mettre à jour
        update_cmd = ["apt", "list", "--upgradable"]
        update_output = subprocess.check_output(update_cmd, stderr=subprocess.DEVNULL).decode()
        # Filtrer les lignes non vides et exclure la ligne d'entête
        updates_lines = [line for line in update_output.split('\n') if line.strip() and not line.startswith('Listing...')]
        total_updates = len(updates_lines)

        # Filtrer les mises à jour de sécurité (en recherchant "security" dans la ligne, insensible à la casse)
        security_updates = len([line for line in updates_lines if "security" in line.lower()])

        # Vérifier si un redémarrage est nécessaire
        reboot_required = os.path.exists('/var/run/reboot-required')

        return {
            "total_updates": total_updates,
            "security_updates": security_updates,
            "reboot_required": reboot_required
        }
    except Exception as e:
        logging.error(f"Erreur lors de la collecte des métriques de mise à jour: {e}")
        return {
            "total_updates": 0,
            "security_updates": 0,
            "reboot_required": False
        }

def get_system_metrics():
    """ Collecte les métriques système """
    try:
        hostname = socket.gethostname()
        ip_address = get_system_ip()
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count(logical=True)
        memory = psutil.virtual_memory()
        mem_total = memory.total
        mem_used = memory.used
        disk = psutil.disk_usage('/')
        disk_total = disk.total
        disk_free = disk.free
        uptime_seconds = int(time.time() - psutil.boot_time())

        # Récupérer les métriques de mise à jour
        update_metrics = get_update_metrics()

        metrics = {
            "hostname": hostname,
            "ip_address": ip_address,
            "cpu_percent": cpu_percent,
            "cpu_count": cpu_count,
            "mem_total": mem_total,
            "mem_used": mem_used,
            "disk_total": disk_total,
            "disk_free": disk_free,
            "uptime_seconds": uptime_seconds,
            "total_updates": update_metrics["total_updates"],
            "security_updates": update_metrics["security_updates"],
            "reboot_required": update_metrics["reboot_required"]
        }

        msg = f"État des mises à jour - Total: {update_metrics['total_updates']}, Sécurité: {update_metrics['security_updates']}, Redémarrage requis: {'Oui' if update_metrics['reboot_required'] else 'Non'}"
        logging.info(msg)

        logging.debug(f"Métriques collectées: {metrics}")
        return metrics
    except Exception as e:
        logging.error(f"Erreur lors de la collecte des métriques: {e}")
        return None

def create_systemd_service(config):
    """ Crée et démarre le service systemd en utilisant le chemin actuel du binaire """

    service_name = "agent_monitor"
    service_path = f"/etc/systemd/system/{service_name}.service"

    # Détecte automatiquement le chemin du binaire
    bin_path = os.path.abspath(sys.argv[0])  # Chemin réel du binaire compilé

    service_content = f"""[Unit]
Description=Agent de Monitoring
After=network.target

[Service]
ExecStart={bin_path} --url {config['server_url']} --port {config['port']} --token {config['token']}
Restart=always
User=root
Group=root
WorkingDirectory={os.path.dirname(bin_path)}

[Install]
WantedBy=multi-user.target
"""

    with open(service_path, "w") as f:
        f.write(service_content)

    subprocess.run(["sudo", "systemctl", "daemon-reload"])
    subprocess.run(["sudo", "systemctl", "enable", service_name])
    subprocess.run(["sudo", "systemctl", "start", service_name])

    print("Service systemd installé et démarré.")
    subprocess.run(["sudo", "systemctl", "status", service_name])
    print(f"Les logs se trouvent ici : {config['log_file']}")
    sys.exit(0)

def main():
    """ Fonction principale """
    parser = argparse.ArgumentParser(description="Agent de monitoring système")
    parser.add_argument("--url", required=True, help="URL du serveur de monitoring")
    parser.add_argument("--port", required=True, type=int, help="Port du serveur de monitoring")
    parser.add_argument("--token", required=True, help="Token d'authentification pour l'API")
    parser.add_argument("--interval", type=int, help="Intervalle de collecte des métriques (en minutes, minimum 1)")
    parser.add_argument("--log_file", help="Fichier de log")
    parser.add_argument("--install-service", action="store_true", help="Créer et démarrer le service systemd")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    config = {
        "server_url": args.url,
        "port": args.port,
        "token": args.token,
        "interval": args.interval or DEFAULT_CONFIG["interval"],
        "log_file": args.log_file or DEFAULT_CONFIG["log_file"]
    }

    if args.install_service:
        create_systemd_service(config)

    setup_logging(config["log_file"])

    logging.info(f"Agent de monitoring démarré - Serveur: {config['server_url']}:{config['port']}")
    # Convertir l'intervalle en minutes et s'assurer qu'il est au moins d'une minute
    interval_minutes = max(1, config["interval"])
    logging.info(f"Intervalle de collecte: {interval_minutes} minute(s)")

    while True:
        try:
            # Calculer le temps jusqu'à la prochaine minute
            current_time = time.time()
            current_dt = datetime.fromtimestamp(current_time)

            # Calculer les minutes à attendre basé sur l'intervalle
            minutes_to_wait = interval_minutes - (current_dt.minute % interval_minutes)
            if minutes_to_wait == interval_minutes and current_dt.second == 0:
                minutes_to_wait = 0

            # Calculer le temps jusqu'au prochain intervalle
            next_collection = current_time + (minutes_to_wait * 60) - current_dt.second

            # Attendre jusqu'au prochain intervalle
            sleep_time = next_collection - current_time
            if sleep_time > 0:
                time.sleep(sleep_time)

            # Collecter et envoyer les métriques
            metrics = get_system_metrics()
            if metrics:
                try:
                    headers = {"Authorization": f"Bearer {config['token']}"}
                    response = requests.post(
                        f"{config['server_url']}:{config['port']}/collect",
                        json=metrics,
                        headers=headers,
                        timeout=10
                    )
                    response.raise_for_status()
                    logging.info("Métriques envoyées avec succès")
                except requests.exceptions.RequestException as e:
                    logging.error(f"Erreur lors de l'envoi des métriques: {e}")
        except KeyboardInterrupt:
            logging.info("Arrêt de l'agent")
            break
        except Exception as e:
            logging.error(f"Erreur inattendue: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
