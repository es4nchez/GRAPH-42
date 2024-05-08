import sys
import os

def ask_easy_key() -> tuple:
    'Quick and durty way to ask a the input for the 42API'
    val_client = input("Enter your client: ") 
    val_secret = input("Enter your secret: ") 
    key_pair = [val_client, val_secret]
    return key_pair


def write_config_file(client_key: str, secret_key: str):
    'Write a simple config file, with the given key'
    file_data = f'''---
  intra:
    client: "{client_key}"
    secret: "{secret_key}"
'''
    with open('config.yml', 'w') as fp:
        fp.write(file_data)
    return


def general_config_check():
    'Checking if the config_file exist and if not creates it.'
    config_file = f'{os.getcwd()}/config.yml'
    if (os.path.isfile(config_file) == True):
        return
    pair_data = ask_easy_key()
    write_config_file(pair_data[0],pair_data[1])
    return

if __name__ == '__main__':
    general_config_check()
