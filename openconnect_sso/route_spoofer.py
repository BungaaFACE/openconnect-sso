import os
import json
import platform
import shutil
from ipaddress import ip_network


def get_requested_routes(filepath, logger) -> list[str]:
    with open(filepath) as routes_file:
        route_list = json.load(routes_file)
    
    for ind in range(len(route_list)):
        try:
            route_list[ind] = ip_network(route_list[ind])
        except Exception as e:
            logger.error('Exception occured during parsing network {route_list[ind]} for routing.')
            raise e
    
    return route_list


def mod_win_scriptfile(script_path, routes_filepath, logger):
    with open(script_path) as file:
        script = file.read()
    script_list = script.split('\n')
    for ind, line in enumerate(script_list):
        if line.startswith('var env ='):
            env_ind = ind+1
            break
    else:
        raise TypeError('Did not found env variable set in vpnc-script')
    
    script_list.insert(env_ind, 'env("CISCO_SPLIT_EXC") = 0;')
    script_list.insert(env_ind, 'env("REDIRECT_GATEWAY_METHOD") = 0;')
    for i, net in enumerate(get_requested_routes(routes_filepath, logger)):
        script_list.insert(env_ind, f'env("CISCO_SPLIT_INC_{i}_ADDR") = \'{net.network_address}\';')
        script_list.insert(env_ind, f'env("CISCO_SPLIT_INC_{i}_MASK") = \'{net.netmask}\';')
        script_list.insert(env_ind, f'env("CISCO_SPLIT_INC_{i}_MASKLEN") = \'{net.prefixlen}\';')
        max_ind = i+1
    script_list.insert(env_ind, f'env("CISCO_SPLIT_INC") = {max_ind};')

    script_text = '\n'.join(script_list)
    with open(script_path, 'w') as file:
        file.write(script_text)
    
    return True

def mod_darwin_scriptfile(script_path, routes_filepath, logger):
    add_test = 'CISCO_SPLIT_EXC=0\nREDIRECT_GATEWAY_METHOD=0\n'

    for i, net in enumerate(get_requested_routes(routes_filepath, logger)):
        add_test += f'CISCO_SPLIT_INC_{i}_ADDR={net.network_address}\n'
        add_test += f'CISCO_SPLIT_INC_{i}_MASK={net.netmask}\n'
        add_test += f'CISCO_SPLIT_INC_{i}_MASKLEN={net.prefixlen}\n'
        max_ind = i+1
    add_test += f'CISCO_SPLIT_INC={max_ind}\n'

    with open(script_path) as file:
        script = file.read()

    with open(script_path, 'w') as file:
        file.write(add_test + script)
    
    return True

def spoof_routes(logger, routes_filepath):
    system_name = platform.system()
    if system_name == 'Windows':
        src_script_path = os.path.join(os.path.dirname(shutil.which('openconnect')), 'vpnc-script-win.js')
        mod_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vpnc-script-win.js')
        shutil.copyfile(src_script_path, mod_script_path)
        mod_win_scriptfile(mod_script_path, routes_filepath, logger)
    else:
        if system_name == 'Linux':
            src_script_path = '/usr/share/vpnc-scripts/vpnc-script'
        elif system_name == 'Darwin':
            src_script_path = '/opt/homebrew/etc/vpnc/vpnc-script'
        else:
            logger.warning(f'Unknown system "{system_name}" for customizing vpnc-script')
            return
        mod_script_path = os.path.join('/', 'tmp', 'vpnc-script')
        shutil.copyfile(src_script_path, mod_script_path)
        os.chmod(mod_script_path, mode=0o755)
        mod_darwin_scriptfile(mod_script_path, routes_filepath, logger)
    return mod_script_path
