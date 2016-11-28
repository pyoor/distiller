import yaml


def read_config(config_file, section):
    with open(config_file, 'r') as stream:
        cfg = yaml.load(stream)

    try:
        data = cfg[section]
    except KeyError:
        print "Error:  Unable to find section %s" % section
        raise

    return data
