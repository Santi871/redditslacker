import configparser


def get_token(token_name, config_name='tokens.ini'):

    config = configparser.ConfigParser()
    config.read(config_name)
    token = config.get('tokens', token_name)
    return token


