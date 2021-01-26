#!/usr/bin/python3

import json
import os
import secrets
import subprocess
import sys
import time
import uuid
from urllib.parse import urlparse

config = {
    'stage': 0,
    'installation_id': '',
    'instance_secret': '',
    'husarnet_id': '',
    'postgres_password': '',
    'secret_key': '',
    'smtp_host': '127.0.0.1',
    'smtp_port': '25',
    'smtp_user': '',
    'smtp_password': '',
}
license_str = ''
license = {}


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def check_root():
    if os.geteuid() != 0:
        print(f'{bcolors.WARNING}Not running as root, re-running '
              f'with sudo...{bcolors.ENDC}')
        code = subprocess.run(['sudo', 'python3', sys.argv[0]]).returncode
        sys.exit(code)


def __run_cmd(cmd):
    subprocess.run(cmd, shell=True).check_returncode()


def load_license():
    try:
        with open('license.json', 'r') as f:
            global license_str
            global license
            license_str = f.read()
            license = json.loads(license_str)
    except FileNotFoundError:
        print(f'{bcolors.FAIL}license.json not found, please place it '
              f'next to install.py{bcolors.ENDC}')
        sys.exit(1)


def install_husarnet():
    if subprocess.run('command -v husarnet', shell=True).returncode == 0:
        print('Husarnet already installed, skipping')
    else:
        __run_cmd('curl https://install.husarnet.com/install.sh | bash')
    __run_cmd('systemctl start husarnet')
    __run_cmd('systemctl enable husarnet')


def retrieve_husarnet_id():
    with open('/var/lib/husarnet/id', 'r') as f:
        id_file = f.read()
    husarnet_id = id_file.split()[0]
    config['husarnet_id'] = husarnet_id


def generate_installation_id():
    config['installation_id'] = str(uuid.uuid4())


def generate_instance_secret():
    config['instance_secret'] = secrets.token_hex(32)


def save_config():
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)


def load_config():
    try:
        with open('config.json', 'r') as f:
            new_config = json.load(f)
            config.update(new_config)
    except FileNotFoundError:
        pass


def finish_stage_1():
    message = f'''Installation ID: {config['installation_id']}
Instance secret: {config['instance_secret']}
Websetup host: {config['husarnet_id']}

Using the information above, please obtain a license and put it in
the same directory as the installation script. Then, re-run install.py.'''
    print(message)


def configure():
    configure_smtp()


def configure_smtp():
    configure_smtp = input_yesno('Do you want to configure SMTP now?')
    if not configure_smtp:
        return

    while True:
        if configure_smtp:
            input_to_config('SMTP host:', 'smtp_host')
            input_to_config('SMTP port:', 'smtp_port')
            input_to_config('SMTP user:', 'smtp_user')
            input_to_config('SMTP password:', 'smtp_password')
        print(f'''
SMTP host: {config['smtp_host']}
SMTP port: {config['smtp_port']}
SMTP user: {config['smtp_user']}
SMTP password: {config['smtp_password']}
''')
        correct = input_yesno('Is this correct?')
        if correct:
            return


def input_yesno(message, default=True):
    placeholder = 'Y/n' if default else 'y/N'
    while True:
        response = input(f'{message} [{placeholder}] ').lower()
        if response not in ('y', 'n', ''):
            print('Invalid response')
        elif response == '':
            return default
        else:
            return response.lower() == 'y'


def input_to_config(message, config_key):
    config[config_key] = input_with_default(message, config[config_key])


def input_with_default(message, default):
    response = input(f'{message} [{default}] ')
    return default if response == '' else response


def install_docker():
    __run_cmd('apt update')
    __run_cmd('apt upgrade -y')
    __run_cmd('apt install -y docker.io docker-compose')
    __run_cmd('systemctl enable docker')


def create_config_dir():
    os.makedirs('/var/cloud', exist_ok=True)


def generate_secret_key():
    config['secret_key'] = secrets.token_hex(32)


def generate_postgres_password():
    config['postgres_password'] = secrets.token_hex(32)


def generate_postgres_config():
    postgres_config = f'''POSTGRES_DB=husarnet
POSTGRES_USER=husarnet
POSTGRES_PASSWORD={config['postgres_password']}
'''
    with open('.env-db', 'w') as f:
        f.write(postgres_config)


def generate_dashboard_config():
    dashboard_url = license['dashboard_url']
    dashboard_hostname = urlparse(dashboard_url).netloc
    dashboard_config = f'''PRODUCTION=1
SITE_URL={dashboard_url}
ROOT_SITE_HOSTNAME={dashboard_hostname}
SITE_HOSTNAME={dashboard_hostname}
SECRET_KEY={config['secret_key']}
HUSARNET_PROXY_URL=https://{{}}.husarnetusers.com
HUSARNET_WEBSETUP_HOST={config['husarnet_id']}
SELF_HOSTED_LICENSE_FILE=/var/cloud/license.json
SELF_HOSTED_INSTANCE_SECRET={config['instance_secret']}

EMAIL_HOST={config['smtp_host']}
EMAIL_PORT={config['smtp_port']}
EMAIL_HOST_USER={config['smtp_user']}
EMAIL_HOST_PASSWORD={config['smtp_password']}

POSTGRESQL_PASSWORD={config['postgres_password']}
POSTGRESQL_HOST=127.0.0.1
POSTGRESQL_USER=husarnet
POSTGRESQL_NAME=husarnet
'''
    with open('/var/cloud/env', 'w') as f:
        f.write(dashboard_config)


def generate_docker_compose():
    compose_file = '''version: '3.7'

services:
  dashboard:
    image: husarnet.azurecr.io/dashboard_selfhosted_nossl
    container_name: dashboard
    command: /opt/app/bin/run-all
    restart: always
    network_mode: host
    depends_on:
      - db
    volumes:
      - /usr/bin/husarnet:/usr/bin/husarnet
      - /var/cloud:/var/cloud
  db:
    restart: always
    image: postgres:10
    ports:
      - 127.0.0.1:5432:5432
    volumes:
      - /var/cloud/postgres:/var/lib/postgresql/data/
    env_file:
      - ./.env-db
'''
    with open('docker-compose.yml', 'w') as f:
        f.write(compose_file)


def install_license():
    with open('/var/cloud/license.json', 'w') as f:
        f.write(license_str)
    with open('/var/lib/husarnet/license.json', 'w') as f:
        f.write(license_str)


def start_dashboard():
    __run_cmd('docker-compose up -d')


def restart_husarnet():
    # Wait for the xtables lock if necessary
    __run_cmd('iptables -w 10 -L > /dev/null')
    __run_cmd('systemctl restart husarnet')


def disable_whitelist():
    __run_cmd('husarnet whitelist disable')


def wait_for_db():
    # Wait until migrations are applied
    time.sleep(10)


def create_superuser():
    __run_cmd('docker exec -it dashboard bin/run-manage createadmin')


def finish_stage_2():
    print(f'{bcolors.OKGREEN}Installation has been completed! You can now '
          f'visit {license["dashboard_url"]}{bcolors.ENDC}')


def run_stage(index, steps):
    print(
        f'{bcolors.OKBLUE}{bcolors.BOLD}'
        f'Running stage {index + 1} if the installation process{bcolors.ENDC}')
    for i, (func, text) in enumerate(steps):
        print(f'{bcolors.OKBLUE}[{i + 1}/{len(steps)}] '
              f'{text}{bcolors.ENDC}')
        func()


STAGE_1_STEPS = [
    (install_husarnet, 'Installing Husarnet'),
    (retrieve_husarnet_id, 'Obtaining Husarnet ID'),
    (generate_installation_id, 'Generating installation ID'),
    (generate_instance_secret, 'Generating instance secret'),
    (save_config, 'Saving configuration file'),
    (finish_stage_1, 'Finishing stage 1'),
]
STAGE_2_STEPS = [
    (load_license, 'Loading license file'),
    (configure, 'Customizing the setup'),
    (save_config, 'Saving configuration file'),
    (install_docker, 'Installing Docker'),
    (create_config_dir, 'Creating config directory'),
    (generate_secret_key, 'Generating secret key'),
    (generate_postgres_password, 'Generating PostgreSQL password'),
    (generate_postgres_config, 'Generating config for PostgreSQL'),
    (generate_dashboard_config, 'Generating config for Husarnet Dashboard'),
    (generate_docker_compose, 'Generating docker-compose file'),
    (install_license, 'Installing the license file'),
    (start_dashboard, 'Starting the dashboard up'),
    (restart_husarnet, 'Restarting the Husarnet client'),
    (disable_whitelist, 'Disabling Husarnet whitelist'),
    (wait_for_db, 'Waiting for the database to be initialized'),
    (create_superuser, 'Creating superuser'),
    (finish_stage_2, 'Finishing the installation'),
]


def stage_1():
    config['stage'] = 1
    run_stage(0, STAGE_1_STEPS)


def stage_2():
    run_stage(1, STAGE_2_STEPS)


STAGES = [stage_1, stage_2]


def main():
    check_root()
    load_config()
    STAGES[config['stage']]()


if __name__ == '__main__':
    main()
