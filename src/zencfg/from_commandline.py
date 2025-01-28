from .from_dict import cfg_from_flat_dict


def cfg_from_commandline(Config, strict=False):
    """Takes a Config class and returns an instance of it, with values updated from command line.
    """
    import sys

    args = sys.argv[1:]  # Skip the script name

    if len(args) % 2 != 0:
        raise ValueError("Arguments must be in pairs like: --model._config_name MyModel --model.layers 24")

    arg_dict = {}
    for i in range(0, len(args), 2):
        key = args[i].lstrip('-')
        arg_dict[key] = args[i+1]

    config = cfg_from_flat_dict(Config, arg_dict, strict=strict)

    return config
