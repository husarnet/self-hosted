#!/usr/bin/python3

import json
import os
import subprocess
import sys

config = {
    'stage': 0,
    'my_address': '',
    'other_base_servers': '',
}


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


def configure():
    configure_my_address()
    configure_other_base_servers()


def configure_my_address():
    while True:
        input_to_config('This server\'s IP address:', 'my_address')
        print(f'''
This server's IP address: {config['my_address']}
''')
        correct = input_yesno('Is this correct?')
        if correct:
            return


def configure_other_base_servers():
    configure_other = input_yesno('Will you have any other base servers?')
    if not configure_other:
        return

    while True:
        input_to_config(
            'Other base servers\' IP addresses (separate by commas):',
            'other_base_servers')
        print(f'''
Other servers' IP addresses: {config['other_base_servers']}
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


def generate_docker_compose():
    compose_file = '''version: '3.7'
services:

  base:
    container_name: base
    image: "husarnet.azurecr.io/husarnet-base"
    restart: always
    ports:
      - "443:4443"
      - "5582"
      - "5437"
      - "5600-5620"
    environment:
      - HUSARNET_SERVER_MY_ADDRESS=5.196.248.106

  redis:
    container_name: redis
    image: "redis:alpine"
    restart: always
    volumes:
      - ./conf/redis.conf:/usr/local/etc/redis/redis.conf
'''
    with open('docker-compose.yml', 'w') as f:
        f.write(compose_file)


def start_dashboard():
    __run_cmd('docker-compose up -d')


def finish_stage_1():
    print(f'{bcolors.OKGREEN}Installation has been completed!{bcolors.ENDC}')


def run_stage(index, steps):
    print(
        f'{bcolors.OKBLUE}{bcolors.BOLD}'
        f'Running stage {index + 1} if the installation process{bcolors.ENDC}')
    for i, (func, text) in enumerate(steps):
        print(f'{bcolors.OKBLUE}[{i + 1}/{len(steps)}] '
              f'{text}{bcolors.ENDC}')
        func()


STAGE_1_STEPS = [
    (configure, 'Customizing the setup'),
    (save_config, 'Saving configuration file'),
    (install_docker, 'Installing Docker'),
    (generate_docker_compose, 'Generating docker-compose file'),
    (start_dashboard, 'Starting the dashboard up'),
    (finish_stage_1, 'Finishing the installation'),
]


def stage_1():
    run_stage(0, STAGE_1_STEPS)


STAGES = [stage_1]


def main():
    check_root()
    load_config()
    STAGES[config['stage']]()


if __name__ == '__main__':
    main()
