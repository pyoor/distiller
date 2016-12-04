import yaml


def read_config(config_file, section):
    sections = ['project', section]

    with open(config_file, 'r') as stream:
        cfg = yaml.load(stream)

    config_data = {}

    try:
        for section in sections:
            for k, v in cfg[section].iteritems():
                config_data[k] = v
    except KeyError:
        print "Error:  Unable to find section %s" % section
        raise

    return config_data
