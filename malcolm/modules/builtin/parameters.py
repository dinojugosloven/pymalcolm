from malcolm.core import method_takes, REQUIRED, OPTIONAL
from malcolm.modules.builtin.vmetas import StringMeta, NumberMeta


def takes_with_default_meta(meta_cls, *meta_args):
    default_args = meta_args + (
        "Default value for parameter. If not specified, parameter is required",)
    return method_takes(
        "name", StringMeta(
            "Specify that this class will take a parameter name"), REQUIRED,
        "description", StringMeta(
            "Description of this parameter"), REQUIRED,
        "default", meta_cls(*default_args), OPTIONAL)


def args_for_takes(params, meta_cls, *meta_args):
    meta_args += (params.description,)
    meta = meta_cls(*meta_args)
    if hasattr(params, "default"):
        return [params.name, meta, params.default]
    else:
        return [params.name, meta, REQUIRED]


@takes_with_default_meta(StringMeta)
def string(params):
    """Define a string parameter to be used within this YAML file"""
    return args_for_takes(params, StringMeta)


@takes_with_default_meta(NumberMeta, "float64")
def float64(params):
    """Define a float64 parameter to be used within this YAML file"""
    return args_for_takes(params, NumberMeta, "float64")


@takes_with_default_meta(NumberMeta, "int32")
def int32(params):
    """Define an int32 parameter to be used within this YAML file"""
    return args_for_takes(params, NumberMeta, "int32")
